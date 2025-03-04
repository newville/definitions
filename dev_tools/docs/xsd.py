import textwrap
from pathlib import Path
from typing import List

import lxml.etree

from ..globals import directories
from ..globals.errors import NXDLParseError
from ..globals.nxdl import XSD_NAMESPACE
from ..utils.types import PathLike


class XSDDocGenerator:
    """
    Read the NXDL field types specification and find
    all the valid data types.  Write a restructured
    text (.rst) document for use in the NeXus manual in
    the NXDL chapter.
    """

    TITLE_MARKERS = "- + ~ ^ * @".split()  # used for underscoring section titles
    INDENTATION = " " * 4
    DATATYPE_DICT = {
        "basicComponent": """/xs:schema//xs:complexType[@name='basicComponent']""",
        "validItemName": """/xs:schema//xs:simpleType[@name='validItemName']""",
        "validNXClassName": """/xs:schema//xs:simpleType[@name='validNXClassName']""",
        "validTargetName": """/xs:schema//xs:simpleType[@name='validTargetName']""",
        "nonNegativeUnbounded": """/xs:schema//xs:simpleType[@name='nonNegativeUnbounded']""",
    }

    def __init__(self) -> None:
        self.ns = {"xs": XSD_NAMESPACE}
        self._rst_lines = None

    def __call__(self, xsd_file: PathLike) -> List[str]:
        self._rst_lines = list()
        xsd_file = Path(xsd_file)
        try:
            self._parse_xsd_file(xsd_file)
        except Exception:
            raise NXDLParseError(xsd_file)
        return self._rst_lines

    def _parse_xsd_file(self, xsd_file: Path):
        tree = lxml.etree.parse(str(xsd_file))

        self._print(f".. auto-generated by {__name__} -- DO NOT EDIT")
        self._print(ELEMENT_PREAMBLE)

        for name in sorted(ELEMENT_DICT):
            self._print("")
            self._print(".. index:: ! %s (NXDL element)\n" % name)
            self._print(".. _%s:\n" % name)
            self.print_title(name, indentLevel=0)
            self._print("\n")
            self._print(ELEMENT_DICT[name])
            self._print("\n")
            self.add_figure(name, indentLevel=0)

        self._print(DATATYPE_PREAMBLE)

        path_list = (
            "/xs:schema/xs:complexType[@name='attributeType']",
            "/xs:schema/xs:element[@name='definition']",
            "/xs:schema/xs:complexType[@name='definitionType']",
            "/xs:schema/xs:simpleType[@name='definitionTypeAttr']",
            "/xs:schema/xs:complexType[@name='dimensionsType']",
            "/xs:schema/xs:complexType[@name='docType']",
            "/xs:schema/xs:complexType[@name='enumerationType']",
            "/xs:schema/xs:complexType[@name='fieldType']",
            "/xs:schema/xs:complexType[@name='choiceType']",
            "/xs:schema/xs:complexType[@name='groupType']",
            "/xs:schema/xs:complexType[@name='linkType']",
            "/xs:schema/xs:complexType[@name='symbolsType']",
            "/xs:schema/xs:complexType[@name='basicComponent']",
            "/xs:schema/xs:simpleType[@name='validItemName']",
            "/xs:schema/xs:simpleType[@name='validNXClassName']",
            "/xs:schema/xs:simpleType[@name='validTargetName']",
            "/xs:schema/xs:simpleType[@name='nonNegativeUnbounded']",
        )
        for path in path_list:
            nodes = self.pick_nodes_from_xpath(tree, path)
            self._print("\n.. Xpath = %s\n" % path)
            self.general_handler(parent=nodes[0])

        self._print(DATATYPE_POSTAMBLE)

    def _tag_match(self, parent, match_list):
        """match this tag to a list"""
        if parent is None:
            raise ValueError("Must supply a valid parent node")
        parent_tag = parent.tag
        tag_found = False
        for item in match_list:
            # this routine only handles certain XML Schema components
            tag_found = parent_tag == "{%s}%s" % (self.ns["xs"], item)
            if tag_found:
                break
        return tag_found

    def _indent(self, indentLevel):
        return self.INDENTATION * indentLevel

    def print_title(self, title, indentLevel):
        self._print(title)
        self._print(self.TITLE_MARKERS[indentLevel] * len(title) + "\n")

    def general_handler(self, parent=None, indentLevel=0):
        """Handle XML nodes like the former XSLT template"""
        # ignore things we don't know how to handle
        known_tags = ("complexType", "simpleType", "group", "element", "attribute")
        if not self._tag_match(parent, known_tags):
            return

        parent_name = parent.get("name")
        if parent_name is None:
            return

        simple_tag = parent.tag[
            parent.tag.find("}") + 1 :
        ]  # cut off the namespace identifier

        # <varlistentry> ...
        name = parent_name  # + ' data type'
        if simple_tag == "attribute":
            name = "@" + name

        if indentLevel == 0 and simple_tag not in ("attribute"):
            self._print(f".. index:: ! {name} (NXDL data type)\n")
            self._print(f"\n.. _NXDL.data.type.{name}:\n")

        self.print_title(name, indentLevel)

        self.print_docs(parent, indentLevel)

        if len(parent.xpath("xs:attribute", namespaces=self.ns)) > 0:
            self.print_title("Attributes of " + name, indentLevel + 1)
            self.apply_templates(parent, "xs:attribute", indentLevel + 1)

        node_list = parent.xpath("xs:restriction", namespaces=self.ns)
        if len(node_list) > 0:
            # print_title("Restrictions of "+name, indentLevel+1)
            self.restriction_handler(node_list[0], indentLevel + 1)
        node_list = parent.xpath(
            "xs:simpleType/xs:restriction/xs:enumeration", namespaces=self.ns
        )
        if len(node_list) > 0:
            #        print_title("Enumerations of "+name, indentLevel+1)
            self.apply_templates(
                parent,
                "xs:simpleType/xs:restriction",
                indentLevel + 1,
                handler=self.restriction_handler,
            )

        if len(parent.xpath("xs:sequence/xs:element", namespaces=self.ns)) > 0:
            self.print_title("Elements of " + name, indentLevel + 1)
            self.apply_templates(parent, "xs:sequence/xs:element", indentLevel + 1)

        node_list = parent.xpath("xs:sequence/xs:group", namespaces=self.ns)
        if len(node_list) > 0:
            self.print_title("Groups under " + name, indentLevel + 1)
            self.print_docs(node_list[0], indentLevel + 1)

        self.apply_templates(parent, "xs:simpleType", indentLevel + 1)
        self.apply_templates(parent, "xs:complexType", indentLevel + 1)
        self.apply_templates(parent, "xs:complexType/xs:attribute", indentLevel + 1)
        self.apply_templates(
            parent, "xs:complexContent/xs:extension/xs:attribute", indentLevel + 1
        )
        self.apply_templates(
            parent, "xs:complexType/xs:sequence/xs:attribute", indentLevel + 1
        )
        self.apply_templates(
            parent, "xs:complexType/xs:sequence/xs:element", indentLevel + 1
        )
        self.apply_templates(
            parent,
            "xs:complexContent/xs:extension/xs:sequence/xs:element",
            indentLevel + 1,
        )

    def restriction_handler(self, parent=None, indentLevel=0):
        """Handle XSD restriction nodes like the former XSLT template"""
        if not self._tag_match(parent, ("restriction",)):
            return
        self.print_docs(parent, indentLevel)
        self._print("\n")
        self._print(self._indent(indentLevel) + "The value may be any")
        base = parent.get("base")
        pattern_nodes = parent.xpath("xs:pattern", namespaces=self.ns)
        enumeration_nodes = parent.xpath("xs:enumeration", namespaces=self.ns)
        if len(pattern_nodes) > 0:
            self._print(
                self._indent(indentLevel)
                + "``%s``" % base
                + " that *also* matches the regular expression::\n"
            )
            self._print(
                self._indent(indentLevel) + " " * 4 + pattern_nodes[0].get("value")
            )
        elif len(pattern_nodes) > 0:
            # how will this be reached?  Perhaps a deprecated procedure
            self._print(
                self._indent(indentLevel) + "``%s``" % base + " from this list:"
            )
            for node in enumeration_nodes:
                self.enumeration_handler(node, indentLevel)
                self.print_docs(node, indentLevel)
            self._print(self._indent(indentLevel))
        elif len(enumeration_nodes) > 0:
            self._print(self._indent(indentLevel) + "one from this list only:\n")
            for node in enumeration_nodes:
                self.enumeration_handler(node, indentLevel)
                self.print_docs(parent, indentLevel)
            self._print(self._indent(indentLevel))
        else:
            self._print("@" + base)
        self._print("\n")

    def enumeration_handler(self, parent=None, indentLevel=0):
        """Handle XSD enumeration nodes like the former XSLT template"""
        if not self._tag_match(parent, ["enumeration"]):
            return
        self._print(self._indent(indentLevel) + "* ``%s``" % parent.get("value"))
        self.print_docs(parent, indentLevel)

    def apply_templates(self, parent, path, indentLevel, handler=None):
        """iterate the nodes found on the supplied XPath expression"""
        if handler is None:
            handler = self.general_handler
        db = {}
        for node in parent.xpath(path, namespaces=self.ns):
            name = node.get("name") or node.get("ref") or node.get("value")
            if name is not None:
                if name in ("nx:groupGroup",):
                    self._print(">" * 45, name)
                if name in db:
                    raise KeyError("Duplicate name found: " + name)
                db[name] = node
        for name in sorted(db):
            node = db[name]
            handler(node, indentLevel)
            # self.print_docs(node, indentLevel)

    def print_docs(self, parent, indentLevel=0):
        docs = self.get_doc_from_node(parent)
        if docs is not None:
            self._print(self._indent(indentLevel) + "\n")
            for line in docs.splitlines():
                self._print(self._indent(indentLevel) + line)
            self._print(self._indent(indentLevel) + "\n")

    def get_doc_from_node(self, node, retval=None):
        annotation_node = node.find("xs:annotation", self.ns)
        if annotation_node is None:
            return retval
        documentation_node = annotation_node.find("xs:documentation", self.ns)
        if documentation_node is None:
            return retval

        # Be sure to grab _all_ content in the <xs:documentation> node.
        # In the documentation nodes, use XML entities ("&lt;"" instead of "<")
        # for documentation characters that would otherwise be considered as XML.
        s = lxml.etree.tostring(documentation_node, method="text", pretty_print=True)
        rst = s.decode().lstrip("\n")  # remove any leading blank lines
        rst = rst.rstrip()  # remove any trailing white space
        text = textwrap.dedent(rst)  # remove common leading space

        # substitute HTML entities in markup: "<" for "&lt;"
        # thanks: http://stackoverflow.com/questions/2087370/decode-html-entities-in-python-string
        try:  # see #661
            import html

            text = html.unescape(text)
        except (ImportError, AttributeError):
            from html import parser as HTMLParser

            htmlparser = HTMLParser.HTMLParser()
            text = htmlparser.unescape(text)

        return text.lstrip()

    def add_figure(self, name, indentLevel=0):
        imageFile = f"img/nxdl/nxdl_{name}.png"
        figure_id = f"fig.nxdl_{name}"
        file_name = directories.manual_source_sphinxroot() / imageFile
        if not file_name.exists():
            return
        text = FIGURE_FMT % (
            figure_id,
            imageFile,
            name,
            "80%",
            name,
            name,
        )
        indent = self._indent(indentLevel)
        for line in text.splitlines():
            self._print(indent + line)
        self._print("\n")

    def pick_nodes_from_xpath(self, parent, path):
        return parent.xpath(path, namespaces=self.ns)

    def _print(self, *args, end="\n"):
        # TODO: change instances of \t to proper indentation
        self._rst_lines.append(" ".join(args) + end)


ELEMENT_DICT = {
    "attribute": """
An ``attribute`` element can *only* be a child of a
``field`` or ``group`` element.
It is used to define *attribute* elements to be used and their data types
and possibly an enumeration of allowed values.

For more details, see:
:ref:`NXDL.data.type.attributeType`
                """,
    "definition": """
A ``definition`` element can *only* be used
at the root level of an NXDL specification.
Note:  Due to the large number of attributes of the ``definition`` element,
they have been omitted from the figure below.

For more details, see:
:ref:`NXDL.data.type.definition`,
:ref:`NXDL.data.type.definitionType`, and
:ref:`NXDL.data.type.definitionTypeAttr`
                """,
    "dimensions": """
The ``dimensions`` element describes the *shape* of an array.
It is used *only* as a child of a ``field`` element.

For more details, see:
:ref:`NXDL.data.type.dimensionsType`
                """,
    "doc": """
A ``doc`` element can be a child of most NXDL elements.  In most cases, the
content of the ``doc`` element will also become part of the NeXus manual.

:element: {any}:

In documentation, it may be useful to
use an element that is not directly specified by the NXDL language.
The *any* element here says that one can use any element
at all in a ``doc`` element and NXDL will not process it but pass it through.

For more details, see:
:ref:`NXDL.data.type.docType`
                """,
    "enumeration": """
An ``enumeration`` element can *only* be a child of a
``field`` or ``attribute`` element.
It is used to restrict the available choices to a predefined list,
such as to control varieties in spelling of a controversial word (such as
*metre* vs. *meter*).

For more details, see:
:ref:`NXDL.data.type.enumerationType`
                """,
    "field": """
The ``field`` element provides the value of a named item.  Many different attributes
are available to further define the ``field``.  Some of the attributes are not
allowed to be used together (such as ``axes`` and ``axis``); see the documentation
of each for details.
It is used *only* as a child of a ``group`` element.

For more details, see:
:ref:`NXDL.data.type.fieldType`
                """,
    "choice": """
A ``choice`` element is used when a named group might take one
of several possible NeXus base classes.  Logically, it must
have at least two group children.

For more details, see:
:ref:`NXDL.data.type.choiceType`
                """,
    "group": """
A ``group`` element can *only* be a child of a
``definition`` or ``group`` element.
It describes a common level of organization in a NeXus data file, similar
to a subdirectory in a file directory tree.

For more details, see:
:ref:`NXDL.data.type.groupType`
                """,
    "link": """
.. index::
    single: link target

A ``link`` element can *only* be a child of a
``definition``,
``field``, or ``group`` element.
It describes the path to the original source of the parent
``definition``,
``field``, or ``group``.

For more details, see:
:ref:`NXDL.data.type.linkType`
                """,
    "symbols": """
A ``symbols`` element can *only* be a child of a ``definition`` element.
It defines the array index symbols to be used when defining arrays as
``field`` elements with common dimensions and lengths.

For more details, see:
:ref:`NXDL.data.type.symbolsType`
                """,
}


ELEMENT_PREAMBLE = """
=============================
NXDL Elements and Field Types
=============================

The documentation in this section has been obtained directly
from the NXDL Schema file:  *nxdl.xsd*.
First, the basic elements are defined in alphabetical order.
Attributes to an element are indicated immediately following the element
and are preceded with an "@" symbol, such as
**@attribute**.
Then, the common data types used within the NXDL specification are defined.
Pay particular attention to the rules for *validItemName*
and  *validNXClassName*.

..
    2010-11-29,PRJ:
    This contains a lot of special case code to lay out the NXDL chapter.
    It could be cleaner but that would also involve some cooperation on
    anyone who edits nxdl.xsd which is sure to break.  The special case ensures
    the parts come out in the chosen order.  BUT, it is possible that new
    items in nxdl.xsd will not automatically go in the manual.
    Can this be streamlined with some common methods?
    Also, there is probably too much documentation in nxdl.xsd.  Obscures the function.

.. index::
    see:attribute; NXDL attribute
    ! single: NXDL elements

.. _NXDL.elements:

NXDL Elements
=============

    """

DATATYPE_PREAMBLE = """

.. _NXDL.data.types.internal:

NXDL Field Types (internal)
===========================

Field types that define the NXDL language are described here.
These data types are defined in the XSD Schema (``nxdl.xsd``)
and are used in various parts of the Schema to define common structures
or to simplify a complicated entry.  While the data types are not intended for
use in NXDL specifications, they define structures that may be used in NXDL specifications.

"""

DATATYPE_POSTAMBLE = """
**The** ``xs:string`` **data type**
    The ``xs:string`` data type can contain characters,
    line feeds, carriage returns, and tab characters.
    See https://www.w3schools.com/xml/schema_dtypes_string.asp
    for more details.

**The** ``xs:token`` **data type**
    The ``xs:string`` data type is derived from the
    ``xs:string`` data type.

    The ``xs:token`` data type also contains characters,
    but the XML processor will remove line feeds, carriage returns, tabs,
    leading and trailing spaces, and multiple spaces.
    See https://www.w3schools.com/xml/schema_dtypes_string.asp
    for more details.
"""


FIGURE_FMT = """
.. compound::

    .. _%s:

    .. figure:: %s
        :alt: fig.nxdl/nxdl_%s
        :width: %s

        Graphical representation of the NXDL ``%s`` element

    .. Images of NXDL structure are generated from nxdl.xsd source
        using the Eclipse XML Schema Editor (Web Tools Platform).  Open the nxdl.xsd file and choose the
        "Design" tab.  Identify the structure to be documented and double-click to expand
        as needed to show the detail.  Use the XSD > "Export Diagram as Image ..." menu item (also available
        as button in top toolbar).
        Set the name: "nxdl_%s.png" and move the file into the correct location using
        your operating system's commands.  Commit the revision to version control.
"""
