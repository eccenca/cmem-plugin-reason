A task performing OWL reasoning. With an OWL ontology and a data graph as input the reasoning result is written to a specified graph.
    
## Options

### Data graph IRI

The IRI of the input data graph. The graph IRI is selected from a list of graphs of types `di:Dataset`, `void:Dataset`
and `owl:Ontology`.

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type`owl:Ontology`.

### Result graph IRI

The IRI of the output graph for the reasoning result.

⚠️ Existing graphs will be overwritten.

### Reasoner

The following reasoner options are supported: 
- [ELK](https://code.google.com/p/elk-reasoner/) (elk)
- [Expression Materializing Reasoner](http://static.javadoc.io/org.geneontology/expression-materializing-reasoner/0.1.3/org/geneontology/reasoner/ExpressionMaterializingReasoner.html) (emr)
- [HermiT](http://www.hermit-reasoner.com/) (hermit)
- [JFact](http://jfact.sourceforge.net/) (jfact)
- [Structural Reasoner](http://owlcs.github.io/owlapi/apidocs_4/org/semanticweb/owlapi/reasoner/structural/StructuralReasoner.html) (structural)
- [Whelk](https://github.com/balhoff/whelk) (whelk)

### Generated Axioms

By default, the reason operation will only assert inferred subclass axioms. The plugin provides the following 
parameters to include inferred axiom generators:

#### Class axiom generators
-  SubClass
- EquivalentClass
- DisjointClasses

#### Data property axiom generators
- DataPropertyCharacteristic
- EquivalentDataProperties
- SubDataProperty

#### Individual axiom generators
- ClassAssertion
- PropertyAssertion

#### Object property axiom generators
- EquivalentObjectProperty
- InverseObjectProperties
- ObjectPropertyCharacteristic
- SubObjectProperty
- ObjectPropertyRange
- ObjectPropertyDomain

### Validate OWL2 profiles

Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and annotate the result graph. 

### Process valid OWL profiles from input

If enabled along with the "Validate OWL2 profiles" parameter, the valid profiles and ontology IRI is taken from the
config port input (parameters "valid_profiles" and "ontology_graph_iri") instead of from running the validation in the 
plugin. The valid profiles input is a comma-separated string (e.g. "Full,DL").

### Add ontology graph import to result graph

Add the triple `<output_graph_iri> owl:imports <ontology_graph_iri>` to the output graph.

### Add result graph import to ontology graph

Add the triple `<ontology_graph_iri> owl:imports <output_graph_iri>` to the ontology graph

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process.

⚠️ Setting the percentage too high may result in an out of memory error.
