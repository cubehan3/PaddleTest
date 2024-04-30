import numpy as np
import paddle


class LayerCase(paddle.nn.Layer):
    """
    case名称: uniform_base
    api简介: 返回数值服从范围[min, max)内均匀分布的随机Tensor
    """

    def __init__(self):
        super(LayerCase, self).__init__()

    def forward(self, ):
        """
        forward
        """
        out = paddle.uniform( shape=[2, 3, 4, 4], )
        return out


def create_tensor_inputs():
    """
    paddle tensor
    """
    inputs = ()
    return inputs


def create_numpy_inputs():
    """
    numpy array
    """
    inputs = ()
    return inputs
