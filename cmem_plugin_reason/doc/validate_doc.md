A task validating the consistency of an OWL ontology (or, in unsatisfiability mode, finding
unsatisfiable classes) and generating an explanation for what was found. The plugin always
outputs entities: the explanation as text in Markdown format on the path "explanation", the
ontology IRI on the path "ontology_graph_iri", the reasoner option on the path "reasoner", and,
if OWL2 profile validation is enabled, the valid profiles on the path "profiles".

No parameter is required when the task is created, so parameters can also be set via the config
port of a workflow. The parameters are validated when the task is executed.

## Options

### Ignore missing imports

If enabled, missing imports (`owl:imports`) in the input graphs are ignored.

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type
`owl:Ontology`.

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process.

⚠️ Setting the percentage too high may result in an out of memory error.

### Validate OWL2 profiles

Validate the input ontology against the OWL 2 profiles (Full, DL, EL, QL, RL) and annotate the
result.

### Output graph IRI

Optional IRI of an output graph to annotate with the validation result (label, comment, and a
link back to the validated ontology). ⚠️ Existing graphs will be overwritten. Leave empty to
skip.

The output graph holds the explanation axioms plus the validation result and is declared a
`void:Dataset`. It is not declared an `owl:Ontology`: it does not contain an ontology of its
own, it describes the validated one.

### Replace blank nodes with IRIs

Advanced option, disabled by default, only relevant if an output graph is set. The explanation
axioms written to the output graph often contain class expressions (e.g. `A SubClassOf: p some B`)
or inverse properties, which are written with blank nodes. If enabled, every blank node is
replaced by an IRI, so no information is lost if the graph is processed by tools that do not keep
blank nodes.

- The IRIs are `https://<domain of the output graph>/.well-known/genid/<uuid>`, the form RDF 1.1
  recommends for replaced blank nodes; for an output graph IRI without a domain (e.g. `urn:`) they
  are `urn:uuid:<uuid>`.
- The UUIDs are computed from what the blank node stands for and from the output graph IRI, so
  re-running the task produces the same IRIs, and different output graphs never share IRIs.

### Reasoner

The following reasoner options are supported:
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](http://jfact.sourceforge.net/) (jfact)

Both are complete OWL DL reasoners capable of generating explanations, which is what
consistency/unsatisfiability validation needs.

### Stop at inconsistencies

Raise an error if inconsistencies are found. If enabled, the plugin does not output entities.

### Mode

Mode _inconsistency_ generates an explanation for an inconsistent ontology.
Mode _unsatisfiability_ generates explanations for many unsatisfiable classes at once. In an
inconsistent ontology every class is unsatisfiable, so this mode then fails with an error; use
mode _inconsistency_ to explain the inconsistency.

### Maximum explanations

The maximum number of independent explanations (justifications) generated per inference.
