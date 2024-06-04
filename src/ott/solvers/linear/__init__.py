# Copyright OTT-JAX
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from . import (
    acceleration,
    continuous_barycenter,
    discrete_barycenter,
    implicit_differentiation,
    lr_utils,
    sinkhorn,
    sinkhorn_lr,
    univariate,
)
from ._solve import solve, solve_univariate

__all__ = [
    "acceleration",
    "continuous_barycenter",
    "discrete_barycenter",
    "implicit_differentiation",
    "lr_utils",
    "sinkhorn",
    "sinkhorn_lr",
    "univariate",
    "solve",
    "solve_univariate",
]
