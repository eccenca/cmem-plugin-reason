<!-- markdownlint-disable MD012 MD013 MD024 MD033 -->
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added

- Reason and Validate plugins: advanced parameter "Timeout (minutes)". If the reasoner hasn't
  finished by then, the task stops with an error. By default (0) there is no limit, as before.
- Reason plugin: axiom generator parameters "Same individuals (owl:sameAs)" and "Data property
  domains (rdfs:domain)" (HermiT and JFact).
- Reason and Validate plugins: warnings of the reasoner are written to the task log, e.g. which
  axioms ELK ignores because it doesn't support them (so the result may be incomplete).
- Reason and Validate plugins: the provenance data in the output graph includes the plugin
  version (`owl:versionInfo`).
- Reason and Validate plugins: the provenance data in the output graph includes the version of
  the bundled reasoner jar (`reasonerVersion`), and its commit (`reasonerCommit`) if the version
  isn't a release version.
- Reason and Validate plugins: advanced parameter "Replace blank nodes with IRIs". Blank nodes in
  the output graph are replaced by stable UUID IRIs under `/.well-known/genid/` of the output
  graph's domain. In the Validate plugin it applies to the explanation axioms, so only if an
  output graph is set.
- Validate plugin: added "Maximum explanations" parameter to limit the number of justifications
  generated per inference.

### Changed

- updated template to v9.10.0
- Use eccenca reasoner (OWLAPI5) instead of ROBOT (OWLAPI4)
- Reason plugin: selecting an axiom generator that ELK doesn't support (e.g. "Individual
  property assertions") with ELK or ELK (EMR) is an error naming the generators; such a
  generator used to give no result, with only a warning in the task log.
- Reason plugin: an error of the reasoner while generating axioms fails the task; it used to be
  only a warning in the task log, and the output graph lacked that generator's axioms.
- Reason plugin: unsatisfiable classes no longer fail the task. With "Class inclusion", each is
  inferred to be a subclass of `owl:Nothing`.
- Reason and Validate plugins: the reasoner reads imported ontologies only from Corporate Memory
  and never fetches one from its IRI (e.g. from the web).
- Reason and Validate plugins: the bundled reasoner uses a version of JFact 5.0.3 with fixes:
  JFact no longer misses subsumptions and equivalences, infers wrong subsumptions with datatype
  restrictions, or finds consistent ontologies inconsistent because of equal numbers of different
  datatypes (e.g. `"3"^^xsd:int` and `"3"^^xsd:integer`), and neither its results nor its running
  time vary between runs any more (wine took between 5 seconds and many minutes; now about 5
  seconds). Its running time no longer grows quadratically with the number of individuals: 40,000
  individuals that only have types took 4 minutes, now 6 seconds; 20,000 pizzas linked to their
  toppings did not finish in 30 minutes, now take 15 seconds; 200,000 individuals of one class
  did not finish in 5 minutes, now take 20 seconds. Individuals with data values, and an
  individual related to tens of thousands of others, are no longer slow either. It no longer
  misses types of individuals that the ontology uses as nominals, or individuals that are the same
  (`owl:sameAs`).
- Reason and Validate plugins: the bundled reasoner uses a version of HermiT 1.4.5.519 with fixes:
  HermiT no longer gives individuals types that aren't entailed, or misses types, with results
  that varied between runs, no longer misses same individuals (`owl:sameAs`), and no longer fails
  on an ontology stating that `owl:Thing` is empty or with a union that simplifies to an empty one.
  It is faster with many individuals: 40,000 individuals that only have types took 4.5 minutes,
  now 6 seconds, with many classes (8,000 subclasses of one class with an instance each: 28
  seconds, now 0.6), and with large `DisjointClasses` or `DifferentIndividuals` axioms (2,000
  members: 31 and 13 seconds, now 0.3). With individuals linked by properties, its running time no longer grows
  quadratically with their number and is the same in every run: the Reason task with class
  assertions on 100 pizzas linked to their toppings took 3.5 minutes, now 1.0 seconds, and 20,000
  pizzas, which didn't finish in 30 minutes, take 69 seconds, with the same result as JFact.
  `rdf:XMLLiteral` values no longer lose attributes or characters outside the Basic Multilingual
  Plane (e.g. emoji). The bundled reasoner no longer contains Axiom and the libraries it needed,
  among them the old woodstox-core-asl and jaxen.
- Reason plugin: faster with HermiT and JFact. The redundant subclass axioms are removed with the
  class hierarchy the reasoning computed, instead of classifying the ontology a second time (HermiT
  on food: 6.9 s → 3.8 s), and the object property hierarchy is only computed when an axiom
  generator needs it (HermiT on 4,000 pizzas linked to their toppings: about a third less time).

- Validate plugin: the profile validation also checks what OWL 2 requires of the RDF graph itself:
  an ontology graph without an ontology header (`owl:Ontology`), or with undeclared classes,
  properties or datatypes, is only OWL 2 Full; the reason is written to the task log.
- Reason and Validate plugins: no parameter is required when the task is created (so they can
  also be set via the config port); parameters are validated when the task is executed.
- Reason plugin: reasoner options are now ELK, ELK (EMR), HermiT, JFact and Structural Reasoner
  (Whelk removed, EMR merged into ELK (EMR)).
- Validate plugin: reasoner options are now limited to HermiT and JFact.
- Validate plugin: entities are now always output (no more "Output entities" toggle); valid
  profiles are output as a list instead of a comma-separated string.
- Reason and Validate plugins: the documentation gives memory sizes for large datasets and how to
  set "Maximum RAM Percentage"; the Reason plugin documents how HermiT and JFact scale with the
  number of individuals and how ELK (EMR)'s memory grows.

### Removed

- Reason plugin: "Validate OWL2 profiles" (and related "Process valid OWL profiles from input" /
  "Valid OWL2 profiles" input) parameters; use the Validate plugin instead.
- Reason plugin: "Output graph import" parameter.
- Validate plugin: "Output filename" parameter and Markdown file resource output.

### Fixed

- Reason and Validate plugins: JFact failed with a `StackOverflowError` on a chain of about 2,000
  subclasses or a `DisjointClasses` axiom with about 1,000 classes. The bundled reasoner now runs
  with a larger stack, which uses memory only as deep as it gets.
- Reason and Validate plugins: cancelling the workflow while the reasoner ran didn't stop the
  reasoner: it ran on, with its CPU and memory, until it finished. It is now stopped within a few
  seconds.
- Reason plugin documentation: corrected the examples for class equivalence (only named
  classes), object property characteristics (functionality is inherited by sub-properties) and
  individual property assertions, and documented which axiom generators each reasoner supports
  (ELK does not support e.g. property assertions, disjointness, ranges and domains).

## [2.5.0] 2026-10-14

### Changed

- Use ROBOT v1.9.11 compiled with [updated dependencies without vulnerabilities](https://github.com/eccenca/robot/tree/feature/updateDependenciesV1.9.11)
- Scan the SBOM of robot.jar (`robot.cdx.json`) with Trivy, since the jar scan cannot identify all bundled libraries
- Updated dependencies and template
- Validate plugin: the output graph is now declared a `void:Dataset` instead of an
  `owl:Ontology`.
- Reason plugin: only one of "Data graph IRI" and "Ontology graph IRI" is required. With only
  one, or the same graph in both, that graph is reasoned on its own, and the result is described as
  "Reasoning results of graph <X>".

### Fixed

- Fix robot.jar vulnerabilities CVE-2024-7254, CVE-2026-43869, CVE-2026-43871.
- Reason plugin: selecting the same graph as data graph and ontology graph failed with
  `OWLOntologyDocumentAlreadyExistsException`.
- Reason and Validate plugins: provenance data is now written with every DataIntegration
  workspace provider. Before, it was only written if the workspace was stored as RDF (workspace
  provider `backend` or `fileAndDataPlatform`), because it was read from the project graph.

## [2.4.1] 2026-10-07

### Fixed

- Broken changelog entries

## [2.4.0] 2026-10-07

### Fixed

- Fix robot.jar vulnerability CVE-2026-68497, CVE-2026-19032, CVE-2026-83557.

### Changed

- Updated dependencies and template.

## [2.3.0] 2026-08-17

### Fixed

- Fix robot.jar vulnerability CVE-2026-49844.

### Changed

- Use cmem-client instead of cmempy for all Corporate Memory access

### Removed

- Remove cmem-cmempy dependency and `setup_cmempy_user_access` calls


## [2.2.7] 2026-07-22

### Fixed

- Fix robot.jar vulnerabilities CVE-2026-54515, CVE-2026-9828.

### Changed

- Remove inflection dependency

## [2.2.6] 2026-06-29

### Fixed

- Fix robot.jar vulnerabilities CVE-2026-54512, CVE-2026-54513, CVE-2026-54514, CVE-2026-54515.

### Changed

- Update template to 8.5.0.

## [2.2.5] 2026-03-01

### Fixed

- Fix robot.jar vulnerability GHSA-72hv-8253-57qq

## [2.2.4] 2026-02-20

### Changed

- use ROBOT v1.9.10 compiled with [updated dependencies without vulnerablities](https://github.com/eccenca/robot/tree/feature/updateDependenciesV1.9.10)

## [2.2.3] 2026-02-17

### Changed

- Update template to 8.3.1.
- Relax URN URI validation.

## [2.2.2] 2026-01-27

### Fixed

- Fix robot.jar vulnerability CVE-2026-1225

### Changed

- Update template to 8.3.0.
- Allow URN URIs in graph parameters.

## [2.2.1] 2025-11-27

### Fixed

- use ROBOT v1.9.8 compiled with [updated dependencies without vulnerablities](https://github.com/eccenca/robot/tree/feature/updateDependenciesV1.9.8)


## [2.2.0] 2025-10-30

### Added

- Handle canceling of workflow.

### Changed

- Get creation date and time after processing.
- Update ROBOT to v1.9.8.
- Update dependencies.


## [2.1.1] 2025-02-18

### Changed

- Default value for "ignore missing imports" is False.
- Change order of parameters in UI.

## [2.1.0] 2025-02-18

### Fixed

- Do not remove import of ontology in result graph if ontology is imported in data graph and "Output graph import" is not
set to "Import ontology graph into output graph" in Reason plugin.

### Added

- Parameter to check missing OWL imports. Missing imports can be ignored or lead to execution error.
- Check if ontology graph and data graph exist before execution.

### Changed

- Throw error if output graph is imported by input graph in Reason plugin
- Use UUIDs for temporary RDF files
- Do not query list of graphs again for output graph label


## [2.0.0] 2024-11-29

### Changed

- replaced the boolean parameters "Add ontology graph import to result graph" and "Add result graph import to ontology graph"
with a pull down menu
- removed axiom generators for object property characteristics and data property characteristics (not working)


## [1.1.0beta2] 2024-11-08

### Fixed

- error caused by plugin parameter provenance generation


## [1.1.0beta1] 2024-11-04

### Added

- support for directories in filepath for output filename in Validate plugin
- axiom generators for object property characteristics and data property characteristics (needs testing)

### Changed

- compatibility with cmem-plugin-base 4.5.0 
- update ROBOT to 1.9.7


## [1.0.1] 2024-09-05

### Fixed

- fix installation issue for platform encodings other than UTF-8


## [1.0.0] 2024-09-03

### Added

- axiom generator description in UI

### Changed

- output graph label derived from input graph
- create plugin label in provenance data


## [1.0.0rc1] 2024-08-28

### Added

 - Validate: added "mode" parameter

### Fixed

- respect owl:imports in OWL2 profile validation

### Changed

 - Validate: the entity output includes the reasoner option on path "reason"
 - detailed axiom generator documentation
 - The axiom generator ObjectPropertyCharacteristic does not yield results. Currently, this axiom generator and its
(working) counterpart DataPropertyCharacteristic are removed from the Reason plugin.


## [1.0.0beta5] 2024-08-15

### Added

 - defined input and output schema
 - Reason: parameters to import the result graph in the ontology graph and to import the ontology graph in the result graph
 - Validate: parameter to enable/disable entity output

### Fixed

 - incorrect stopping of workflow if "validate_profiles" and "stop_at_inconsistencies" is enabled in Validate plugin
 - fixed error when output graph is imported by input graph; the import is removed in-memory before reasoning

### Changed

- raise OSError on post result graph error
- removed write_md and produce_graph bool parameters
- If "input_profiles" is enabled the Reason plugin expects "ontology_iri" and "profile" on the input.
The ontology IRI on the input overrides the plugin setting.
- update execution report
- output graph IRI selectable from existing graphs
- When "input_profiles" is enabled the ontology IRI and list of valid OWL2 profiles is now taken from the config port.
The list of valid profiles is a comma-separated string (e.g. "Full,DL").


## [1.0.0beta4] 2024-07-12

### Fixed

- fixed errors on CMEM instances with self-signed/invalid certificates

### Added

- valid OWL profiles can be read on the Reason plugin input instead of validating the ontology in the plugin

### Changed

- use DCMI Metadata Terms for provenance
- new icons


## [1.0.0beta3] 2024-07-09

### Fixed

- temporary files are now removed when an error occurs

### Added

- parameter for validating the input ontology against OWL2 profiles (DL, EL, QL, RL, and Full)
- Validate plugin outputs valid profiles with path "profile"

### Changed

- Validate plugin outputs the Markdown result with path "markdown"


## [1.0.0beta2] 2024-07-04

### Fixed

- `prov:wasGeneratedBy` in output graphs now refers to a plugin IRI instead of a literal

### Changed

- keep original output ("No explanations found.") if no inconsistencies found with Validate plugin
- provenance data in output graphs now includes plugin parameter settings
- new icons


## [1.0.0beta1] 2024-07-01

### Fixed

- valid range of "Maximum RAM Percentage" parameter in Validate plugin (1-100)

### Changed

- complete validation for IRI parameters
- remove "Annnotate inferred subclass axioms" parameter in Reason plugin


## [1.0.0alpha3] 2024-06-28

### Added

- "Annotate inferred axioms" parameter in Reason plugin
- "Maximum RAM percentage" parameter

### Changed

- axiom generators are now not advanced parameters


## [1.0.0alpha2] (skipped)


## [1.0.0alpha1] 2024-06-27

### Added

- initial version

