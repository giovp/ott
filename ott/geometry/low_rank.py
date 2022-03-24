# coding=utf-8
# Copyright 2022 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""A class describing low-rank geometries."""
from typing import Union, Optional
import jax
import jax.numpy as jnp
from ott.geometry import geometry


@jax.tree_util.register_pytree_node_class
class LRCGeometry(geometry.Geometry):
  r"""Low-rank Cost Geometry defined by two factors.
  """

  def __init__(self,
               cost_1: jnp.ndarray,
               cost_2: jnp.ndarray,
               bias: float = 0.0,
               scale_cost: Optional[Union[float, str]] = None,
               **kwargs
               ):
    r"""Initializes a geometry by passing it low-rank factors.

    Args:
      cost_1: jnp.ndarray<float>[num_a, r]
      cost_2: jnp.ndarray<float>[num_b, r]
      bias: constant added to entire cost matrix.
      scale_cost: option to rescale the cost matrix. Implemented scalings are
        'max_bound'. Alternatively, a float factor can be
        given to rescale the cost such that ``cost_matrix /= factor``.
      **kwargs: additional kwargs to Geometry
    """
    assert cost_1.shape[1] == cost_2.shape[1]
    self._cost_1 = cost_1
    self._cost_2 = cost_2
    self._bias = bias
    self._kwargs = kwargs

    super().__init__(**kwargs)
    self._scale_cost = scale_cost

  @property
  def cost_1(self):
    return self._cost_1 * jnp.sqrt(self.scale_cost)

  @property
  def cost_2(self):
    return self._cost_2 * jnp.sqrt(self.scale_cost)

  @property
  def bias(self):
    return self._bias * self.scale_cost

  @property
  def cost_rank(self):
    return self._cost_1.shape[1]

  @property
  def cost_matrix(self):
    """Returns cost matrix if requested."""
    return (jnp.matmul(self.cost_1, self.cost_2.T) + self.bias)

  @property
  def shape(self):
    return (self._cost_1.shape[0], self._cost_2.shape[0])

  @property
  def is_symmetric(self):
    return (self._cost_1.shape[0] == self._cost_2.shape[0] and
            jnp.all(self._cost_1 == self._cost_2))

  @property
  def scale_cost(self):
    if isinstance(self._scale_cost, float):
      return self._scale_cost
    elif self._scale_cost == 'max_bound':
      return jax.lax.stop_gradient(
          1.0 / (jnp.max(jnp.abs(self._cost_1))
                 * jnp.max(jnp.abs(self._cost_2))
                 + jnp.abs(self._bias)))
    elif self._scale_cost == 'mean':
      factor1 = jnp.dot(jnp.ones(self.shape[0]), self._cost_1)
      factor2 = jnp.dot(self._cost_2.T, jnp.ones(self.shape[1]))
      mean = (jnp.dot(factor1, factor2) / (self.shape[0] * self.shape[1])
              + self._bias)
      return jax.lax.stop_gradient(1.0 / mean)
    elif self._scale_cost == 'max_cost':
      # TODO(lpapaxanthos): implement memory efficient max.
      raise NotImplementedError(f'Scaling {self._scale_cost} not implemented.')
    elif isinstance(self._scale_cost, str):
      raise ValueError(f'Scaling {self._scale_cost} not provided.')
    else:
      return 1.0

  def apply_square_cost(self, arr: jnp.ndarray, axis: int = 0) -> jnp.ndarray:
    """Applies elementwise-square of cost matrix to array (vector or matrix)."""
    (n, m), r = self.shape, self.cost_rank
    # When applying square of a LRCgeometry, one can either elementwise square
    # the cost matrix, or instantiate an augmented (rank^2) LRCGeometry
    # and apply it. First is O(nm), the other is O((n+m)r^2).
    if n * m < (n + m) * r**2:  #  better use regular apply
      return super().apply_square_cost(arr, axis)
    else:
      new_cost_1 = self.cost_1[:, :, None] * self.cost_1[:, None, :]
      new_cost_2 = self.cost_2[:, :, None] * self.cost_2[:, None, :]
      return LRCGeometry(
          cost_1=new_cost_1.reshape((n, r**2)),
          cost_2=new_cost_2.reshape((m, r**2))).apply_cost(arr, axis)

  def _apply_cost_to_vec(self,
                         vec: jnp.ndarray,
                         axis: int = 0,
                         fn=None) -> jnp.ndarray:
    """Applies [num_a, num_b] fn(cost) (or transpose) to vector.

    Args:
      vec: jnp.ndarray [num_a,] ([num_b,] if axis=1) vector
      axis: axis on which the reduction is done.
      fn: function optionally applied to cost matrix element-wise, before the
        doc product

    Returns:
      A jnp.ndarray corresponding to cost x vector
    """
    def efficient_apply(vec, axis, fn):
      c1 = self.cost_1 if axis == 1 else self.cost_2
      c2 = self.cost_2 if axis == 1 else self.cost_1
      c2 = fn(c2) if fn is not None else c2
      bias = fn(self.bias) if fn is not None else self.bias
      out = jnp.dot(c1, jnp.dot(c2.T, vec))
      return out + bias * jnp.sum(vec) * jnp.ones_like(out)

    return jnp.where(fn is None or geometry.is_linear(fn),
                     efficient_apply(vec, axis, fn),
                     super()._apply_cost_to_vec(vec, axis, fn))

  def apply_cost_1(self, vec, axis=0):
    return jnp.dot(self.cost_1 if axis == 0 else self.cost_1.T, vec)

  def apply_cost_2(self, vec, axis=0):
    return jnp.dot(self.cost_2 if axis == 0 else self.cost_2.T, vec)

  def tree_flatten(self):
    return (self._cost_1, self._cost_2, self._kwargs), {
        'bias': self._bias, 'scale_cost': self._scale_cost}

  @classmethod
  def tree_unflatten(cls, aux_data, children):
    return cls(*children[:-1], **children[-1], **aux_data)


def add_lrc_geom(geom1: LRCGeometry, geom2: LRCGeometry):
  """Add geometry in geom1 to that in geom2, keeping other geom1 params."""
  return LRCGeometry(
      cost_1=jnp.concatenate((geom1.cost_1, geom2.cost_1), axis=1),
      cost_2=jnp.concatenate((geom1.cost_2, geom2.cost_2), axis=1),
      **geom1._kwargs)
