A task validating the consistency of an OWL ontology (or, in unsatisfiability mode, finding
unsatisfiable classes) and generating an explanation for what was found. The plugin always
outputs entities: the explanation as text in Markdown format on the path "explanation", the
ontology IRI on the path "ontology_graph_iri", the reasoner option on the path "reasoner", and,
if OWL2 profile validation is enabled, the valid profiles on the path "profiles".

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
Mode _unsatisfiability_ generates explanations for many unsatisfiable classes at once.

### Maximum explanations

The maximum number of independent explanations (justifications) generated per inference.
