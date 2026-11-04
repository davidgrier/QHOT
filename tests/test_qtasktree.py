'''Unit tests for QTaskTree.'''
import unittest

from qtpy import QtWidgets

from QHOT.lib.tasks.QTask import QTask
from QHOT.lib.tasks.QTaskTree import QTaskTree

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class _NoParams(QTask):
    '''Task with no declared parameters.'''
    parameters = []


class _TwoParams(QTask):
    '''Task with two declared parameters.'''
    parameters = [
        dict(name='alpha', type='float', value=1.0),
        dict(name='beta',  type='int',   value=10),
    ]

    def __init__(self, alpha: float = 1.0, beta: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.alpha = alpha
        self.beta  = beta


class TestQTaskTreeInit(unittest.TestCase):

    def test_task_property_returns_task(self):
        task = _TwoParams()
        tree = QTaskTree(task)
        self.assertIs(tree.task, task)

    def test_params_group_named_after_task_class(self):
        task = _TwoParams()
        tree = QTaskTree(task)
        root = tree.invisibleRootItem()
        self.assertEqual(root.child(0).text(0), '_TwoParams')

    def test_param_count_matches_parameters_spec(self):
        task = _TwoParams()
        tree = QTaskTree(task)
        root = tree.invisibleRootItem()
        group = root.child(0)
        self.assertEqual(group.childCount(), len(_TwoParams.parameters))

    def test_empty_parameters_produces_empty_group(self):
        task = _NoParams()
        tree = QTaskTree(task)
        root = tree.invisibleRootItem()
        group = root.child(0)
        self.assertEqual(group.childCount(), 0)

    def test_initial_values_from_instance_attrs(self):
        task = _TwoParams(alpha=3.5, beta=42)
        tree = QTaskTree(task)
        self.assertAlmostEqual(tree._params.child('alpha').value(), 3.5)
        self.assertEqual(tree._params.child('beta').value(), 42)

    def test_initial_values_not_just_class_defaults(self):
        task = _TwoParams(alpha=99.0)
        tree = QTaskTree(task)
        self.assertAlmostEqual(tree._params.child('alpha').value(), 99.0)


class TestQTaskTreeSync(unittest.TestCase):

    def test_editing_param_updates_task_attribute(self):
        task = _TwoParams(alpha=1.0)
        tree = QTaskTree(task)
        tree._params.child('alpha').setValue(7.5)
        self.assertAlmostEqual(task.alpha, 7.5)

    def test_editing_int_param_updates_task_attribute(self):
        task = _TwoParams(beta=10)
        tree = QTaskTree(task)
        tree._params.child('beta').setValue(99)
        self.assertEqual(task.beta, 99)

    def test_multiple_edits_all_propagate(self):
        task = _TwoParams(alpha=0.0, beta=0)
        tree = QTaskTree(task)
        tree._params.child('alpha').setValue(2.5)
        tree._params.child('beta').setValue(5)
        self.assertAlmostEqual(task.alpha, 2.5)
        self.assertEqual(task.beta, 5)

    def test_ignore_sync_prevents_update(self):
        task = _TwoParams(alpha=1.0)
        tree = QTaskTree(task)
        tree._ignoreSync = True
        tree._params.child('alpha').setValue(99.0)
        self.assertAlmostEqual(task.alpha, 1.0)

    def test_two_trees_on_same_task_both_sync(self):
        task = _TwoParams(alpha=1.0)
        tree1 = QTaskTree(task)
        tree2 = QTaskTree(task)
        tree1._params.child('alpha').setValue(2.0)
        self.assertAlmostEqual(task.alpha, 2.0)
        tree2._params.child('alpha').setValue(3.0)
        self.assertAlmostEqual(task.alpha, 3.0)


if __name__ == '__main__':
    unittest.main()
