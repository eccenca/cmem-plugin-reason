A task performing OWL reasoning. With an OWL ontology and a data graph as input the reasoning result is written to a specified graph.
    
## Options

### Data graph IRI

The IRI of the input data graph. The graph IRI is selected from a list of graphs of types `di:Dataset`, `void:Dataset`
and `owl:Ontology`.

### Ontology graph IRI

The IRI of the input ontology graph. The graph IRI is selected from a list of graphs of type`owl:Ontology`.

### Output graph IRI

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

The plugin provides the following parameters to include inferred axiom generators:

#### Class axiom generators
- **Class inclusion (rdfs:subClassOf)**  
The reasoner will infer assertions about the hierarchy of classes, i.e.
`SubClassOf:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Student SubClassOf: Person`.  


- **Class equivalence (owl:equivalentClass)**  
The reasoner will infer assertions about the equivalence of classes, i.e.
`EquivalentTo:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `Person EquivalentTo: Student and Professor`.


- **Class disjointness (owl:disjointWith)**  
The reasoner will infer assertions about the disjointness of classes, i.e.
`DisjointClasses:` statements.  
If there are classes `Person`, `Student` and `Professor`, such that `Person DisjointUnionOf:
Student, Professor` holds, the reasoner will infer `DisjointClasses: Student, Professor`.

  
- **Data property equivalence (owl:equivalentProperty)**  
The reasoner will infer axioms about the equivalence of data properties,
 i.e. `EquivalentProperties` statements.  
If there are data properties `identifier` and `enrollmentNumber`, such that `enrollmentNumber
SubPropertyOf: identifier` and `identifier SubPropertyOf: enrollmentNumber` holds, the reasoner
will infer `Student EquivalentProperties: identifier, enrollmentNumber`.


- **Data property inclusion (rdfs:subPropertyOf)**  
The reasoner will infer axioms about the hierarchy of data properties,
i.e. `SubPropertyOf:` statements.  
If there are data properties `identifier`, `studentIdentifier` and `enrollmentNumber`, such that
`studentIdentifier SubPropertyOf: identifier` and `enrollmentNumber SubPropertyOf:
studentIdentifier` holds, the reasoner will infer `enrollmentNumber SubPropertyOf: identifier`.


#### Individual axiom generators
- **Individual class assertions (rdf:type)**  
The reasoner will infer assertions about the classes of individuals, i.e.
`Types:` statements.  
Assume, there are classes `Person`, `Student` and `University` as well as the property
`enrolledIn`, such that `Student EquivalentTo: Person and enrolledIn some University` holds. For
the individual `John` with the assertions `John Types: Person; Facts: enrolledIn
LeipzigUniversity`, the reasoner will infer `John Types: Student`.


- **Individual property assertions**  
The reasoner will infer assertions about the properties of individuals,
i.e. `Facts:` statements.  
Assume, there are properties `enrolledIn` and `offers`, such that `enrolled SubPropertyChain:
enrolledIn o inverse (offers)` holds. For the individuals `John`and `LeipzigUniversity` with the
assertions `John Facts: enrolledIn KnowledgeRepresentation` and `LeipzigUniversity Facts: offers
KnowledgeRepresentation`,  the reasoner will infer `John Facts: enrolledIn LeipzigUniversity`.


#### Object property axiom generators
- **Object property equivalence (owl:equivalentProperty)**  
The reasoner will infer assertions about the equivalence of object
properties, i.e. `EquivalentTo:` statements.  
If there are object properties `hasAlternativeLecture` and `hasSameTopicAs`, such that
`hasAlternativeLecture Characteristics: Symmetric` and `hasSameTopicAs InverseOf:
hasAlternativeLecture` holds, the reasoner will infer `EquivalentProperties: hasAlternativeLecture,
hasSameTopicAs`.


- **Object property inversion (owl:inverseOf)**  
The reasoner will infer axioms about the inversion about object
properties, i.e. `InverseOf:` statements.  
If there is a object property `hasAlternativeLecture`, such that `hasAlternativeLecture
Characteristics: Symmetric` holds, the reasoner will infer `hasAlternativeLecture InverseOf:
hasAlternativeLecture`.


- **Object property inclusion (rdfs:subPropertyOf)**  
The reasoner will infer axioms about the inclusion of object properties,
i.e. `SubPropertyOf:` statements.  
If there are object properties `enrolledIn`, `studentOf` and `hasStudent`, such that `enrolledIn
SubPropertyOf: studentOf` and `enrolledIn InverseOf: hasStudent` holds, the reasoner will infer
`hasStudent SubPropertyOf: inverse (studentOf)`.


- **Object property ranges (rdfs:range)**  
The reasoner will infer axioms about the ranges of object properties,
i.e. `Range:` statements.  
If there are classes `Student` and `Lecture` as wells as object properties `hasStudent` and
`enrolledIn`, such that `hasStudent Range: Student and enrolledIn some Lecture` holds, the
reasoner will infer `hasStudent Range: Student`.


- **Object property domains (rdfs:domain)**  
The reasoner will infer axioms about the domains of object
properties, i.e. `Domain:` statements.  
If there are classes `Person`, `Student` and `Professor` as wells as the object property
`hasRoleIn`, such that `Professor SubClassOf: Person`, `Student SubClassOf: Person` and
`hasRoleIn Domain: Professor or Student` holds, the reasoner will infer `hasRoleIn Domain: Person`.


### Validate OWL2 profiles

Validate the input ontology against OWL profiles (DL, EL, QL, RL, and Full) and annotate the result graph. 

### Process valid OWL profiles from input

If enabled along with the "Validate OWL2 profiles" parameter, the valid profiles, ontology IRI and reasoner option is
taken from the config port input (parameters "valid_profiles", "ontology_graph_iri" and "reasoner") and the OWL2
profiles validation is not done in the plugin. The valid profiles input is a comma-separated string (e.g. "Full,DL").

### Add ontology graph import to result graph

Add the triple `<output_graph_iri> owl:imports <ontology_graph_iri>` to the output graph.

### Add result graph import to ontology graph

Add the triple `<ontology_graph_iri> owl:imports <output_graph_iri>` to the ontology graph

### Maximum RAM Percentage

Maximum heap size for the Java virtual machine in the DI container running the reasoning process.

⚠️ Setting the percentage too high may result in an out of memory error.
