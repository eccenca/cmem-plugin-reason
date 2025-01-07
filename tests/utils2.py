"""Common functions"""

from pathlib import Path

from cmem.cmempy.dp.proxy.graph import get, post_streamed
from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

from . import __path__


def get_remote_graph(iri: str) -> Graph:
    """Get remote graph IRI"""
    graph = Graph().parse(
        data=get(iri, owl_imports_resolution=False).text,
        format="turtle",
    )
    graph.remove((URIRef(iri), DCTERMS.created, None))
    graph.remove((None, RDF.type, OWL.AnnotationProperty))
    return graph


def import_graph(iri: str, filename: str) -> None:
    """Import graph to CMEM"""
    res = post_streamed(iri, str(Path(__path__[0]) / filename), replace=True)
    if res.status_code != 204:  # noqa: PLR2004
        raise ValueError(f"Response {res.status_code}: {res.url}")
