import os
os.environ['FLAGS_cinn_new_group_scheduler'] = '1'
os.environ['FLAGS_group_schedule_tiling_first'] = '1'
os.environ['FLAGS_enable_pir_api'] = '1'
os.environ['FLAGS_cinn_bucket_compile'] = '1'
import sys
import unittest
import numpy as np
from dataclasses import dataclass
import typing as t

@dataclass
class Stage:
    name: str
    env_vars: t.Dict[str, str]

cinn_stages = [
    Stage(
        name="dynamic_to_static",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=False,
            FLAGS_prim_enable_dynamic=False,
        ),
    ),
    Stage(
        name="prim",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
        ),
    ),
    Stage(
        name="infer_symbolic",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=False,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=False,
            FLAGS_check_infer_symbolic=True,
        ),
    ),
	Stage(
        name="frontend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=True,
        ), 
    ),
    Stage(
        name="backend",
        env_vars=dict(
            PADDLE_DEBUG_ENABLE_CINN=True,
            FLAGS_prim_all=True,
            FLAGS_prim_enable_dynamic=True,
            FLAGS_use_cinn=True,
            FLAGS_check_infer_symbolic=False,
            FLAGS_enable_fusion_fallback=False,
        ), 
    ),
]

def GetCinnStageByName(name):
    for stage in cinn_stages:
        if stage.name == name:
            return stage
    return None

def GetCurrentCinnStage():
    name = os.getenv('PADDLE_DEBUG_CINN_STAGE_NAME')
    if name is None:
        return None
    stage_names = [stage.name for stage in cinn_stages]
    assert name in stage_names, (
        f"PADDLE_DEBUG_CINN_STAGE_NAME should be in {stage_names}"
    )
    return GetCinnStageByName(name)

def GetPrevCinnStage(stage):
    for i in range(1, len(cinn_stages)):
        if stage is cinn_stages[i]:
            return cinn_stages[i - 1]
    return None

def IsCinnStageEnableDiff():
    value = os.getenv('PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF')
    enabled = value in {
        '1',
        'true',
        'True',
    }
    if enabled:
        assert GetCurrentCinnStage() is not None
    return enabled

last_cinn_stage_exit_code = None
def LastCINNStageFailed():
    global last_cinn_stage_exit_code
    if last_cinn_stage_exit_code is not None:
        return last_cinn_stage_exit_code != 0
    last_stage = GetPrevCinnStage(GetCurrentCinnStage())
    if last_stage is None:
        return False
    env_vars = dict(
        PADDLE_DEBUG_CINN_STAGE_NAME=last_stage.name,
        PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF='0',
    )
    env_vars_str = " ".join(
        f"{env_var}={value}"
        for env_var, value in env_vars.items()
    )
    last_cinn_stage_exit_code = os.system(
        f"{env_vars_str} {sys.executable} {__file__} > /dev/null 2>&1"
    )
    return last_cinn_stage_exit_code != 0

def SetDefaultEnv(**env_var2value):
    for env_var, value in env_var2value.items():
        if os.getenv(env_var) is None:
            os.environ[env_var] = str(value)

SetDefaultEnv(
    PADDLE_DEBUG_CINN_STAGE_NAME="backend",
    PADDLE_DEBUG_CINN_STAGE_ENABLE_DIFF=False,
    PADDLE_DEBUG_ENABLE_CINN=True,
    FLAGS_enable_pir_api=True,
    FLAGS_prim_all=True,
    FLAGS_prim_enable_dynamic=True,
    FLAGS_use_cinn=False,
    FLAGS_check_infer_symbolic=False,
    FLAGS_enable_fusion_fallback=False,
)

import paddle

def SetEnvVar(env_var2value):
    for env_var, value in env_var2value.items():
        os.environ[env_var] = str(value)
    paddle.set_flags({
        env_var:value
        for env_var, value in env_var2value.items()
        if env_var.startswith('FLAGS_')
    })

if GetCurrentCinnStage() is not None:
    SetEnvVar(GetCurrentCinnStage().env_vars)

def GetEnvVarEnableJit():
    enable_jit = os.getenv('PADDLE_DEBUG_ENABLE_JIT')
    return enable_jit not in {
        "0",
        "False",
        "false",
        "OFF",
    }

def GetEnvVarEnableCinn():
    enable_cinn = os.getenv('PADDLE_DEBUG_ENABLE_CINN')
    if enable_cinn is None:
        return True
    return enable_cinn not in {
        "0",
        "False",
        "false",
        "OFF",
    }


def GetTolerance(dtype):
    if dtype == np.float16:
        return GetFloat16Tolerance()
    if dtype == np.float32:
        return GetFloat32Tolerance()
    return 1e-6

def GetFloat16Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT16_TOL'))
    except:
        return 1e-3

def GetFloat32Tolerance():
    try:
        return float(os.getenv('PADDLE_DEBUG_FLOAT32_TOL'))
    except:
        return 1e-6

def IsInteger(dtype):
    return np.dtype(dtype).char in np.typecodes['AllInteger']

def ApplyToStatic(net, use_cinn):
    build_strategy = paddle.static.BuildStrategy()
    build_strategy.build_cinn_pass = use_cinn
    return paddle.jit.to_static(
        net,
        input_spec=net.get_input_spec(),
        build_strategy=build_strategy,
        full_graph=True,
    )

class InstanceTrait:

    @classmethod
    def instance(cls):
        if cls.instance_ is None:
            cls.instance_ = cls()
        return cls.instance_

    @classmethod
    def static_instance_with_cinn(cls):
        if cls.static_instance_with_cinn_ is None:
            cls.static_instance_with_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=True
            )
        return cls.static_instance_with_cinn_

    @classmethod
    def static_instance_without_cinn(cls):
        if cls.static_instance_without_cinn_ is None:
            cls.static_instance_without_cinn_ = ApplyToStatic(
                cls.instance(),
                use_cinn=False
            )
        return cls.static_instance_without_cinn_


class CinnTestBase:

    def setUp(self):
        paddle.seed(2024)
        self.prepare_data()

    def test_train(self):
        dy_outs = self.train(use_cinn=False)
        cinn_outs = self.train(use_cinn=GetEnvVarEnableCinn())

        for cinn_out, dy_out in zip(cinn_outs, dy_outs):
          if type(cinn_out) is list and type(dy_out) is list:
            for x, y in zip(cinn_out, dy_out):
              self.assert_all_close(x, y)
          else:
            self.assert_all_close(cinn_out, dy_out)

    def train(self, use_cinn):
        if GetEnvVarEnableJit():
            net = self.prepare_static_net(use_cinn)
        else:
            net = self.prepare_net()
        paddle.seed(2024)
        out = net(*self.inputs)
        return out
    
    def prepare_data(self):
        self.inputs = self.get_inputs()
        for input in self.inputs:
            input.stop_gradient = True

    def prepare_net(self):
        return self.get_test_class().instance()

    def prepare_static_net(self, use_cinn):
        if use_cinn:
            return self.get_test_class().static_instance_with_cinn()
        else:
            return self.get_test_class().static_instance_without_cinn()

    def assert_all_close(self, x, y):
        if (hasattr(x, "numpy") and hasattr(y, "numpy")):
            x_numpy = x.numpy()
            y_numpy = y.numpy()
            assert x_numpy.dtype == y_numpy.dtype
            if IsInteger(x_numpy.dtype):
                np.testing.assert_equal(x_numpy, y_numpy)
            else:
                tol = GetTolerance(x_numpy.dtype)
                np.testing.assert_allclose(x_numpy, y_numpy, atol=tol, rtol=tol)
        else:
            assert x == y





last_stage_failed = (IsCinnStageEnableDiff() and LastCINNStageFailed())
class PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[None, None], dtype='float32'),
            paddle.static.InputSpec(shape=[], dtype='float32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_d6ef82762118bf3178b885e2830f195b(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 2100], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]



class PrimitiveOp_9b2b1423b2e11e0a6e6145e1eb78adf0(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[1, 500, 128], dtype='int32'),
            paddle.static.InputSpec(shape=[], dtype='int32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_f89f4926bf787e1534f41ac5607cd491(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_9b2b1423b2e11e0a6e6145e1eb78adf0
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_f89f4926bf787e1534f41ac5607cd491(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_9b2b1423b2e11e0a6e6145e1eb78adf0
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]



class PrimitiveOp_aef9904d2c616e07250ed29687a43845(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[None], dtype='int32'),
            paddle.static.InputSpec(shape=[], dtype='int32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_b2d3d26925367fbdf5a521c3b4153d5f(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([2, 6], dtype='int32').reshape([2]),
            paddle.to_tensor(-1, dtype='int32').reshape([]),
        ]



class PrimitiveOp_7fbef9171809257ac3f453915ad4778a(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[None], dtype='float32'),
            paddle.static.InputSpec(shape=[None], dtype='float32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_7f02e87f10d21b7532d91eeccc6e262d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_7fbef9171809257ac3f453915ad4778a
    def get_inputs(self):
        return [
            paddle.to_tensor([0.24978351593017578, 0.11446373909711838, 0.06451474130153656, 0.04623079672455788, 0.3613818883895874, 0.3921468257904053], dtype='float32').reshape([6]),
            paddle.to_tensor([0.2304920107126236, 0.3881237208843231, 0.457919716835022, 0.21335071325302124, 0.38008421659469604, 0.12877273559570312], dtype='float32').reshape([6]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_1b8f4efe6527caef7f9adb195a9a261d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_7fbef9171809257ac3f453915ad4778a
    def get_inputs(self):
        return [
            paddle.to_tensor([0.2845926582813263, 0.1542942374944687, 0.25496557354927063, 0.29948753118515015, 0.21094956994056702, 0.2771330177783966], dtype='float32').reshape([6]),
            paddle.to_tensor([0.2527327835559845, 0.1622818112373352, 0.470980703830719, 0.32545068860054016, 0.27355799078941345, 0.35376250743865967], dtype='float32').reshape([6]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_ddaf6340385b6e5c5485c8916ce4195d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([6, 9], dtype='int32').reshape([2]),
            paddle.to_tensor(-1, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_c023cec5f92b910af8d6e25a1687d427(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 3549], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]



class PrimitiveOp_38ac68fef92e8bf11136af8a0c7af675(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[1], dtype='int32'),
            paddle.static.InputSpec(shape=[], dtype='int32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_69f16b1b114ce7540bab84778b2910a5(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_38ac68fef92e8bf11136af8a0c7af675
    def get_inputs(self):
        return [
            paddle.to_tensor([7], dtype='int32').reshape([1]),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_585b04a86e045cd5a81c6d186bb983ef(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_38ac68fef92e8bf11136af8a0c7af675
    def get_inputs(self):
        return [
            paddle.to_tensor([3], dtype='int32').reshape([1]),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_41d070e989f09728f320085d5d7c13b3(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 4116], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_f89f4926bf787e1534f41ac5607cd491(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_9b2b1423b2e11e0a6e6145e1eb78adf0
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_d6ef82762118bf3178b885e2830f195b(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 2100], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]



class PrimitiveOp_4c7c4de59e686a1f970a2d1a3dd379c2(InstanceTrait, paddle.nn.Layer):
    
    def __init__(self):
        super().__init__()

    def forward(self, arg_0, arg_1):
        input_0 = arg_0
        input_1 = arg_1
        return input_0 > input_1

    def get_input_spec(self):
        return [
            paddle.static.InputSpec(shape=[None, None, None], dtype='int32'),
            paddle.static.InputSpec(shape=[], dtype='int32'),
        ]
        
    instance_ = None
    static_instance_with_cinn_ = None
    static_instance_without_cinn_ = None


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_640feaf45dd0db4615475d6d5441b24c(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_4c7c4de59e686a1f970a2d1a3dd379c2
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_640feaf45dd0db4615475d6d5441b24c(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_4c7c4de59e686a1f970a2d1a3dd379c2
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_b2d3d26925367fbdf5a521c3b4153d5f(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([2, 6], dtype='int32').reshape([2]),
            paddle.to_tensor(-1, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_7f02e87f10d21b7532d91eeccc6e262d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_7fbef9171809257ac3f453915ad4778a
    def get_inputs(self):
        return [
            paddle.to_tensor([0.24978351593017578, 0.11446373909711838, 0.06451474130153656, 0.04623079672455788, 0.3613818883895874, 0.3921468257904053], dtype='float32').reshape([6]),
            paddle.to_tensor([0.2304920107126236, 0.3881237208843231, 0.457919716835022, 0.21335071325302124, 0.38008421659469604, 0.12877273559570312], dtype='float32').reshape([6]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_1b8f4efe6527caef7f9adb195a9a261d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_7fbef9171809257ac3f453915ad4778a
    def get_inputs(self):
        return [
            paddle.to_tensor([0.2845926582813263, 0.1542942374944687, 0.25496557354927063, 0.29948753118515015, 0.21094956994056702, 0.2771330177783966], dtype='float32').reshape([6]),
            paddle.to_tensor([0.2527327835559845, 0.1622818112373352, 0.470980703830719, 0.32545068860054016, 0.27355799078941345, 0.35376250743865967], dtype='float32').reshape([6]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_ddaf6340385b6e5c5485c8916ce4195d(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([6, 9], dtype='int32').reshape([2]),
            paddle.to_tensor(-1, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_c023cec5f92b910af8d6e25a1687d427(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 3549], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_3471f283cdfe263238284ba6e468eca8(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([7], dtype='int32').reshape([1]),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_787f55498ae4026bafbdef3aca6923ce(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_aef9904d2c616e07250ed29687a43845
    def get_inputs(self):
        return [
            paddle.to_tensor([3], dtype='int32').reshape([1]),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_41d070e989f09728f320085d5d7c13b3(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_e68fc36e6aeecfc1344ee017c9e05b27
    def get_inputs(self):
        return [
            paddle.uniform([1, 4116], dtype='float32', min=0, max=0.5),
            paddle.to_tensor(0.0, dtype='float32').reshape([]),
        ]


@unittest.skipIf(last_stage_failed, "last stage failed")
class TestPrimitiveOp_640feaf45dd0db4615475d6d5441b24c(CinnTestBase, unittest.TestCase):
    
    def get_test_class(self):
        return PrimitiveOp_4c7c4de59e686a1f970a2d1a3dd379c2
    def get_inputs(self):
        return [
            paddle.randint(low=0, high=3, shape=[1, 500, 128], dtype='int32'),
            paddle.to_tensor(0, dtype='int32').reshape([]),
        ]




if __name__ == '__main__':
    unittest.main()