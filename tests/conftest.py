import pytest

from dashcam import context


@pytest.fixture(autouse=True)
def clean_thread_context():
    context._local.trace = None
    context._local.span_idx = 0
    yield
    context._local.trace = None
