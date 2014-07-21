import unittest

import numpy
import numpy.linalg
from numpy.testing import assert_array_almost_equal
from numpy.testing import dec, assert_array_equal, assert_allclose
from numpy import inf

import theano
from theano import tensor, function
from theano.tensor.basic import _allclose
from theano.tests.test_rop import break_op
from theano.tests import unittest_tools as utt
from theano import config

# The one in comment are not tested...
from theano.sandbox.linalg.ops import (cholesky,
                                       Cholesky,  # op class
                                       CholeskyGrad,
                                       matrix_inverse,
                                       pinv,
                                       Solve,
                                       diag,
                                       ExtractDiag,
                                       extract_diag,
                                       AllocDiag,
                                       alloc_diag,
                                       det,
                                       svd,
                                       qr,
                                       #PSD_hint,
                                       trace,
                                       matrix_dot,
                                       spectral_radius_bound,
                                       imported_scipy,
                                       Eig,
                                       inv_as_solve,
                                       norm
                                       )

from theano.sandbox.linalg import eig, eigh, eigvalsh
from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr
from nose.tools import assert_raises


def test_rop_lop():
    mx = tensor.matrix('mx')
    mv = tensor.matrix('mv')
    v = tensor.vector('v')
    y = matrix_inverse(mx).sum(axis=0)

    yv = tensor.Rop(y, mx, mv)
    rop_f = function([mx, mv], yv)

    sy, _ = theano.scan(lambda i, y, x, v: (tensor.grad(y[i], x) * v).sum(),
                        sequences=tensor.arange(y.shape[0]),
                        non_sequences=[y, mx, mv])
    scan_f = function([mx, mv], sy)

    rng = numpy.random.RandomState(utt.fetch_seed())
    vx = numpy.asarray(rng.randn(4, 4), theano.config.floatX)
    vv = numpy.asarray(rng.randn(4, 4), theano.config.floatX)

    v1 = rop_f(vx, vv)
    v2 = scan_f(vx, vv)

    assert _allclose(v1, v2), ('ROP mismatch: %s %s' % (v1, v2))

    raised = False
    try:
        tensor.Rop(
            theano.clone(y, replace={mx: break_op(mx)}),
            mx,
            mv)
    except ValueError:
        raised = True
    if not raised:
        raise Exception((
            'Op did not raised an error even though the function'
            ' is not differentiable'))

    vv = numpy.asarray(rng.uniform(size=(4,)), theano.config.floatX)
    yv = tensor.Lop(y, mx, v)
    lop_f = function([mx, v], yv)

    sy = tensor.grad((v * y).sum(), mx)
    scan_f = function([mx, v], sy)

    v1 = lop_f(vx, vv)
    v2 = scan_f(vx, vv)
    assert _allclose(v1, v2), ('LOP mismatch: %s %s' % (v1, v2))


def test_spectral_radius_bound():
    tol = 10 ** (-6)
    rng = numpy.random.RandomState(utt.fetch_seed())
    x = theano.tensor.matrix()
    radius_bound = spectral_radius_bound(x, 5)
    f = theano.function([x], radius_bound)

    shp = (3, 4)
    m = rng.rand(*shp)
    m = numpy.cov(m).astype(config.floatX)
    radius_bound_theano = f(m)

    # test the approximation
    mm = m
    for i in range(5):
        mm = numpy.dot(mm, mm)
    radius_bound_numpy = numpy.trace(mm) ** (2 ** (-5))
    assert abs(radius_bound_numpy - radius_bound_theano) < tol

    # test the bound
    eigen_val = numpy.linalg.eig(m)
    assert (eigen_val[0].max() - radius_bound_theano) < tol

    # test type errors
    xx = theano.tensor.vector()
    ok = False
    try:
        spectral_radius_bound(xx, 5)
    except TypeError:
        ok = True
    assert ok
    ok = False
    try:
        spectral_radius_bound(x, 5.)
    except TypeError:
        ok = True
    assert ok

    # test value error
    ok = False
    try:
        spectral_radius_bound(x, -5)
    except ValueError:
        ok = True
    assert ok


class Matrix_power():

    def test_numpy_compare(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        A = tensor.matrix("A", dtype=theano.config.floatX)
        Q = matrix_power(A, 3)
        fn = function([A], [Q])
        a = rng.rand(4, 4).astype(theano.config.floatX)

        n_p = numpy.linalg.matrix_power(a, 3)
        t_p = fn(a)
        assert numpy.allclose(n_p, t_p)

    def test_non_square_matrix(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        A = tensor.matrix("A", dtype=theano.config.floatX)
        Q = matrix_power(A, 3)
        f = function([A], [Q])
        a = rng.rand(4, 3).astype(theano.config.floatX)
        self.assertRaises(ValueError, f, a)

class T_NormTests(unittest.TestCase):

    def test_wrong_type_of_ord_for_vector(self):
        self.assertRaises(ValueError, norm, [2, 1], 'fro')

    def test_wrong_type_of_ord_for_matrix(self):
        self.assertRaises(ValueError, norm, [[2, 1], [3, 4]], 0)

    def test_non_tensorial_input(self):
        self.assertRaises(ValueError, norm, 3, None)

    def test_tensor_input(self):
        self.assertRaises(NotImplementedError, norm, numpy.random.rand(3, 4, 5), None)

    def test_numpy_compare(self):
        rng = numpy.random.RandomState(utt.fetch_seed())

        M = tensor.matrix("A", dtype=theano.config.floatX)
        V = tensor.vector("V", dtype=theano.config.floatX)

        a = rng.rand(4, 4).astype(theano.config.floatX)
        b = rng.rand(4).astype(theano.config.floatX)

        A = (   [None, 'fro', 'inf', '-inf', 1, -1, None, 'inf', '-inf', 0, 1, -1, 2, -2],
                [M, M, M, M, M, M, V, V, V, V, V, V, V, V],
                [a, a, a, a, a, a, b, b, b, b, b, b, b, b],
                [None, 'fro', inf, -inf, 1, -1, None, inf, -inf, 0, 1, -1, 2, -2])

        for i in range(0, 14):
            f = function([A[1][i]], norm(A[1][i], A[0][i]))
            t_n = f(A[2][i])
            n_n = numpy.linalg.norm(A[2][i], A[3][i])
            assert _allclose(n_n, t_n)
