"""Tests for validating graph parameter URIs"""

from cmem_plugin_reason.utils import is_valid_uri


def test_graph_parameter_url() -> None:
    """Test validation of URL"""
    assert is_valid_uri("https://example.org/graph")


def test_graph_parameter_url_fail() -> None:
    """Test validation of URL - fail"""
    assert not is_valid_uri("https:/example.org/graph")


def test_graph_parameter_urn() -> None:
    """Test validation of URN (1)"""
    assert is_valid_uri("urn:isbn:9780134685991")


def test_graph_parameter_urn_2() -> None:
    """Test validation of URN (2)"""
    assert is_valid_uri("urn:x:9780134685991")


def test_graph_parameter_urn_3() -> None:
    """Test validation of URN (3)"""
    assert is_valid_uri("urn:x")


def test_graph_parameter_empty() -> None:
    """Test validation of URN - fail"""
    assert not is_valid_uri("")


def test_graph_parameter_none() -> None:
    """Test validation of URN - fail 2"""
    assert not is_valid_uri(None)
