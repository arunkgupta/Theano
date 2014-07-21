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

from theano.tensor.nlinalg import ( MatrixInverse,
                                    matrix_inverse,
                                    MatrixPinv,
                                    pinv,
                                    AllocDiag,
                                    alloc_diag,
                                    ExtractDiag,
                                    extract_diag,
                                    diag,
                                    trace,
                                    Det,
                                    det,
                                    Eig,
                                    eig,
                                    Eigh,
                                    EighGrad,
                                    eigh,
                                    matrix_dot,
                                    _zero_disconnected,
                                    qr
                                    )

from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr
from nose.tools import assert_raises


def test_pseudoinverse_correctness():
    rng = numpy.random.RandomState(utt.fetch_seed())
    d1 = rng.randint(4) + 2
    d2 = rng.randint(4) + 2
    r = rng.randn(d1, d2).astype(theano.config.floatX)

    x = tensor.matrix()
    xi = pinv(x)

    ri = function([x], xi)(r)
    assert ri.shape[0] == r.shape[1]
    assert ri.shape[1] == r.shape[0]
    assert ri.dtype == r.dtype
    # Note that pseudoinverse can be quite unprecise so I prefer to compare
    # the result with what numpy.linalg returns
    assert _allclose(ri, numpy.linalg.pinv(r))


def test_inverse_correctness():
    rng = numpy.random.RandomState(utt.fetch_seed())

    r = rng.randn(4, 4).astype(theano.config.floatX)

    x = tensor.matrix()
    xi = matrix_inverse(x)

    ri = function([x], xi)(r)
    assert ri.shape == r.shape
    assert ri.dtype == r.dtype

    rir = numpy.dot(ri, r)
    rri = numpy.dot(r, ri)

    assert _allclose(numpy.identity(4), rir), rir
    assert _allclose(numpy.identity(4), rri), rri


def test_matrix_dot():
    rng = numpy.random.RandomState(utt.fetch_seed())
    n = rng.randint(4) + 2
    rs = []
    xs = []
    for k in xrange(n):
        rs += [rng.randn(4, 4).astype(theano.config.floatX)]
        xs += [tensor.matrix()]
    sol = matrix_dot(*xs)

    theano_sol = function(xs, sol)(*rs)
    numpy_sol = rs[0]
    for r in rs[1:]:
        numpy_sol = numpy.dot(numpy_sol, r)

    assert _allclose(numpy_sol, theano_sol)


def test_qr_modes():
    rng = numpy.random.RandomState(utt.fetch_seed())

    A = tensor.matrix("A", dtype=theano.config.floatX)
    a = rng.rand(4, 4).astype(theano.config.floatX)

    f = function([A], qr(A))
    t_qr = f(a)
    n_qr = numpy.linalg.qr(a)
    assert _allclose(n_qr, t_qr)

    for mode in ["reduced", "r", "raw", "full", "economic"]:
        f = function([A], qr(A, mode))
        t_qr = f(a)
        n_qr = numpy.linalg.qr(a, mode)
        if isinstance(n_qr, (list, tuple)):
            assert _allclose(n_qr[0], t_qr[0])
            assert _allclose(n_qr[1], t_qr[1])
        else:
            assert _allclose(n_qr, t_qr)

    try:
        n_qr = numpy.linalg.qr(a, "complete")
        f = function([A], qr(A, "complete"))
        t_qr = f(a)
        assert _allclose(n_qr, t_qr)
    except TypeError, e:
        assert "name 'complete' is not defined" in str(e)


def test_svd():
    rng = numpy.random.RandomState(utt.fetch_seed())
    A = tensor.matrix("A", dtype=theano.config.floatX)
    U, V, T = svd(A)
    fn = function([A], [U, V, T])
    a = rng.rand(4, 4).astype(theano.config.floatX)
    n_u, n_v, n_t = numpy.linalg.svd(a)
    t_u, t_v, t_t = fn(a)

    assert _allclose(n_u, t_u)
    assert _allclose(n_v, t_v)
    assert _allclose(n_t, t_t)


def test_inverse_singular():
    singular = numpy.array([[1, 0, 0]] + [[0, 1, 0]] * 2,
                           dtype=theano.config.floatX)
    a = tensor.matrix()
    f = function([a], matrix_inverse(a))
    try:
        f(singular)
    except numpy.linalg.LinAlgError:
        return
    assert False


def test_inverse_grad():
    rng = numpy.random.RandomState(utt.fetch_seed())
    r = rng.randn(4, 4)
    tensor.verify_grad(matrix_inverse, [r], rng=numpy.random)

    rng = numpy.random.RandomState(utt.fetch_seed())

    r = rng.randn(4, 4)
    tensor.verify_grad(matrix_inverse, [r], rng=numpy.random)


def test_det():
    rng = numpy.random.RandomState(utt.fetch_seed())

    r = rng.randn(5, 5).astype(config.floatX)
    x = tensor.matrix()
    f = theano.function([x], det(x))
    assert numpy.allclose(numpy.linalg.det(r), f(r))


def test_det_grad():
    rng = numpy.random.RandomState(utt.fetch_seed())

    r = rng.randn(5, 5).astype(config.floatX)
    tensor.verify_grad(det, [r], rng=numpy.random)


def test_det_shape():
    rng = numpy.random.RandomState(utt.fetch_seed())
    r = rng.randn(5, 5).astype(config.floatX)

    x = tensor.matrix()
    f = theano.function([x], det(x))
    f_shape = theano.function([x], det(x).shape)
    assert numpy.all(f(r).shape == f_shape(r))


class test_diag(unittest.TestCase):
    """
    Test that linalg.diag has the same behavior as numpy.diag.
    numpy.diag has two behaviors:
    (1) when given a vector, it returns a matrix with that vector as the
    diagonal.
    (2) when given a matrix, returns a vector which is the diagonal of the
    matrix.

    (1) and (2) are tested by test_alloc_diag and test_extract_diag
    respectively.

    test_diag test makes sure that linalg.diag instantiates
    the right op based on the dimension of the input.
    """
    def __init__(self, name, mode=None, shared=tensor._shared,
                 floatX=None, type=tensor.TensorType):
        self.mode = mode
        self.shared = shared
        if floatX is None:
            floatX = config.floatX
        self.floatX = floatX
        self.type = type
        super(test_diag, self).__init__(name)

    def test_alloc_diag(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        x = theano.tensor.vector()
        g = alloc_diag(x)
        f = theano.function([x], g)

        # test "normal" scenario (5x5 matrix) and special cases of 0x0 and 1x1
        for shp in [5, 0, 1]:
            m = rng.rand(shp).astype(self.floatX)
            v = numpy.diag(m)
            r = f(m)
            # The right matrix is created
            assert (r == v).all()

        # Test we accept only vectors
        xx = theano.tensor.matrix()
        ok = False
        try:
            alloc_diag(xx)
        except TypeError:
            ok = True
        assert ok

        # Test infer_shape
        f = theano.function([x], g.shape)
        topo = f.maker.fgraph.toposort()
        if config.mode != 'FAST_COMPILE':
            assert sum([node.op.__class__ == AllocDiag for node in topo]) == 0
        for shp in [5, 0, 1]:
            m = rng.rand(shp).astype(self.floatX)
            assert (f(m) == m.shape).all()

    def test_alloc_diag_grad(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        x = rng.rand(5)
        tensor.verify_grad(alloc_diag, [x], rng=rng)

    def test_diag(self):
        # test that it builds a matrix with given diagonal when using
        # vector inputs
        x = theano.tensor.vector()
        y = diag(x)
        assert y.owner.op.__class__ == AllocDiag

        # test that it extracts the diagonal when using matrix input
        x = theano.tensor.matrix()
        y = extract_diag(x)
        assert y.owner.op.__class__ == ExtractDiag

        # other types should raise error
        x = theano.tensor.tensor3()
        ok = False
        try:
            y = extract_diag(x)
        except TypeError:
            ok = True
        assert ok

    # not testing the view=True case since it is not used anywhere.
    def test_extract_diag(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        m = rng.rand(2, 3).astype(self.floatX)
        x = self.shared(m)
        g = extract_diag(x)
        f = theano.function([], g)
        assert [isinstance(node.inputs[0].type, self.type)
                for node in f.maker.fgraph.toposort()
                if isinstance(node.op, ExtractDiag)] == [True]

        for shp in [(2, 3), (3, 2), (3, 3), (1, 1), (0, 0)]:
            m = rng.rand(*shp).astype(self.floatX)
            x.set_value(m)
            v = numpy.diag(m)
            r = f()
            # The right diagonal is extracted
            assert (r == v).all()

        # Test we accept only matrix
        xx = theano.tensor.vector()
        ok = False
        try:
            extract_diag(xx)
        except TypeError:
            ok = True
        assert ok

        # Test infer_shape
        f = theano.function([], g.shape)
        topo = f.maker.fgraph.toposort()
        if config.mode != 'FAST_COMPILE':
            assert sum([node.op.__class__ == ExtractDiag
                        for node in topo]) == 0
        for shp in [(2, 3), (3, 2), (3, 3)]:
            m = rng.rand(*shp).astype(self.floatX)
            x.set_value(m)
            assert f() == min(shp)

    def test_extract_diag_grad(self):
        rng = numpy.random.RandomState(utt.fetch_seed())
        x = rng.rand(5, 4).astype(self.floatX)
        tensor.verify_grad(extract_diag, [x], rng=rng)

    @attr('slow')
    def test_extract_diag_empty(self):
        c = self.shared(numpy.array([[], []], self.floatX))
        f = theano.function([], extract_diag(c), mode=self.mode)

        assert [isinstance(node.inputs[0].type, self.type)
                for node in f.maker.fgraph.toposort()
                if isinstance(node.op, ExtractDiag)] == [True]


def test_trace():
    rng = numpy.random.RandomState(utt.fetch_seed())
    x = theano.tensor.matrix()
    g = trace(x)
    f = theano.function([x], g)

    for shp in [(2, 3), (3, 2), (3, 3)]:
        m = rng.rand(*shp).astype(config.floatX)
        v = numpy.trace(m)
        assert v == f(m)

    xx = theano.tensor.vector()
    ok = False
    try:
        trace(xx)
    except TypeError:
        ok = True
    assert ok


class test_Eig(utt.InferShapeTester):
    op_class = Eig
    op = eig
    dtype = 'float64'

    def setUp(self):
        super(test_Eig, self).setUp()
        self.rng = numpy.random.RandomState(utt.fetch_seed())
        self.A = theano.tensor.matrix(dtype=self.dtype)
        X = numpy.asarray(self.rng.rand(5, 5),
                          dtype=self.dtype)
        self.S = X.dot(X.T)

    def test_infer_shape(self):
        A = self.A
        S = self.S
        self._compile_and_check([A],  # theano.function inputs
                                self.op(A),  # theano.function outputs
                                # S must be square
                                [S],
                                self.op_class,
                                warn=False)

    def test_eval(self):
        A = theano.tensor.matrix(dtype=self.dtype)
        self.assertEquals([e.eval({A: [[1]]}) for e in self.op(A)],
                          [[1.0], [[1.0]]])
        x = [[0, 1], [1, 0]]
        w, v = [e.eval({A: x}) for e in self.op(A)]
        assert_array_almost_equal(numpy.dot(x, v), w * v)


class test_Eigh(test_Eig):
    op = staticmethod(eigh)

    def test_uplo(self):
        S = self.S
        a = theano.tensor.matrix(dtype=self.dtype)
        wu, vu = [out.eval({a: S}) for out in self.op(a, 'U')]
        wl, vl = [out.eval({a: S}) for out in self.op(a, 'L')]
        assert_array_almost_equal(wu, wl)
        assert_array_almost_equal(vu * numpy.sign(vu[0, :]),
                                  vl * numpy.sign(vl[0, :]))

    def test_grad(self):
        S = self.S
        utt.verify_grad(lambda x: self.op(x)[0], [S], rng=self.rng)
        utt.verify_grad(lambda x: self.op(x)[1], [S], rng=self.rng)
        utt.verify_grad(lambda x: self.op(x, 'U')[0], [S], rng=self.rng)
        utt.verify_grad(lambda x: self.op(x, 'U')[1], [S], rng=self.rng)


class test_Eigh_float32(test_Eigh):
    dtype = 'float32'


class T_lstsq(unittest.TestCase):

    def test_correct_solution(self):
        x = tensor.lmatrix()
        y = tensor.lmatrix()
        z = tensor.lscalar()
        b = theano.sandbox.linalg.ops.lstsq()(x, y, z)
        f = function([x, y, z], b)
        TestMatrix1 = numpy.asarray([[2, 1], [3, 4]])
        TestMatrix2 = numpy.asarray([[17, 20], [43, 50]])
        TestScalar = numpy.asarray(1)
        f = function([x, y, z], b)
        m = f(TestMatrix1, TestMatrix2, TestScalar)
        self.assertTrue(numpy.allclose(TestMatrix2, numpy.dot(TestMatrix1, m[0])))

    def test_wrong_coefficient_matrix(self):
        x = tensor.vector()
        y = tensor.vector()
        z = tensor.scalar()
        b = theano.sandbox.linalg.ops.lstsq()(x, y, z)
        f = function([x, y, z], b)
        self.assertRaises(numpy.linalg.linalg.LinAlgError, f, [2, 1], [2, 1], 1)

    def test_wrong_rcond_dimension(self):
        x = tensor.vector()
        y = tensor.vector()
        z = tensor.vector()
        b = theano.sandbox.linalg.ops.lstsq()(x, y, z)
        f = function([x, y, z], b)
        self.assertRaises(numpy.linalg.LinAlgError, f, [2, 1], [2, 1], [2, 1])

