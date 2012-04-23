++++++++++++++++
Developing Cubes
++++++++++++++++

This chapter describes some guidelines how to contribute to the Cubes.

General
=======

* If you are puzzled why is something implemented certain way, ask before
  complaining. There might be a reason that is not explained and that should
  be described in documentation. Or there might not even be a reason for
  current implementation at all, and you suggestion might help.
* Until 1.0 the interface is not 100% decided and might change
* Focus is on usability, simplicity and understandability. There might be
  places where this might not be completely achieved and this feature of code
  should be considered as bug. For example: overcomplicated interface, too
  long call sequence which can be simplified, required over-configuration,...
* Magic is not bad, if used with caution and the mechanic is well documented.
  Also there should be a way how to do it manually for every magical feature.


New or changed feature checklist
================================

* add/change method
* add docstring documentation
* reflect documentation
    * are any examples affected?
* commit

