from __future__ import annotations

import csv
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

WORKBOOK_NAME = "Open_Source_Ecosystem_Intelligence.twb"
PACKAGE_NAME = "Open_Source_Ecosystem_Intelligence.twbx"
DATA_FILE_NAME = "tableau_repo_momentum_extract.csv"
DATASOURCE = "federated.ecosystem_intelligence"


def _uuid(name: str) -> str:
    value = uuid.uuid5(uuid.NAMESPACE_URL, f"dev-ecosystem-pipeline/{name}")
    return "{" + str(value).upper() + "}"


def _tableau_type(values: list[str]) -> str:
    cleaned = [value for value in values if value not in {"", "nan", "None"}]
    if not cleaned:
        return "string"
    lowered = {value.lower() for value in cleaned}
    if lowered <= {"true", "false"}:
        return "boolean"
    try:
        for value in cleaned:
            int(value)
        return "integer"
    except ValueError:
        pass
    try:
        for value in cleaned:
            float(value)
        return "real"
    except ValueError:
        pass
    try:
        parsed = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in cleaned]
        return "date" if all(item.time().isoformat() == "00:00:00" for item in parsed) else "datetime"
    except ValueError:
        return "string"


def _field(column: str, datatype: str) -> str:
    if column == "Number of Records":
        return (
            "<column datatype='integer' name='[Number of Records]' role='measure' "
            "type='quantitative' user:auto-column='numrec'><calculation class='tableau' formula='1' /></column>"
        )
    role = "dimension" if datatype in {"string", "boolean", "date", "datetime"} else "measure"
    field_type = "nominal" if role == "dimension" else "quantitative"
    return (
        f"<column datatype='{datatype}' name='[{escape(column)}]' "
        f"role='{role}' type='{field_type}' />"
    )


def _instance(column: str, datatype: str) -> tuple[str, str]:
    if datatype in {"string", "boolean", "date", "datetime"}:
        name = f"none:{column}:nk"
        xml = (
            f"<column-instance column='[{escape(column)}]' derivation='None' "
            f"name='[{escape(name)}]' pivot='key' type='nominal' />"
        )
    else:
        name = f"sum:{column}:qk"
        xml = (
            f"<column-instance column='[{escape(column)}]' derivation='Sum' "
            f"name='[{escape(name)}]' pivot='key' type='quantitative' />"
        )
    return name, xml


def _worksheet(
    name: str,
    title: str,
    fields: list[tuple[str, str]],
    rows: str,
    cols: str,
    mark: str,
    encodings: list[tuple[str, str]],
    formats: list[tuple[str, str]] | None = None,
) -> str:
    dependencies: list[str] = []
    references: dict[str, str] = {}
    for column, datatype in fields:
        dependencies.append(_field(column, datatype))
        instance_name, instance_xml = _instance(column, datatype)
        dependencies.append(instance_xml)
        references[column] = f"[{DATASOURCE}].[{instance_name}]"

    encoding_xml = "\n".join(
        f"              <{kind} column='{references[column]}' />" for kind, column in encodings
    )
    format_xml = "\n".join(
        f"                <format attr='{attr}' value='{value}' />" for attr, value in (formats or [])
    )
    style = (
        f"""            <style>
              <style-rule element='mark'>
{format_xml}
              </style-rule>
            </style>"""
        if format_xml
        else ""
    )
    row_ref = references[rows] if rows else ""
    col_ref = references[cols] if cols else ""
    return f"""    <worksheet name='{escape(name)}'>
      <layout-options>
        <title><formatted-text><run fontcolor='#172B4D' fontsize='16' bold='true'>{escape(title)}</run></formatted-text></title>
      </layout-options>
      <table>
        <view>
          <datasources><datasource caption='Open-Source Ecosystem Intelligence' name='{DATASOURCE}' /></datasources>
          <datasource-dependencies datasource='{DATASOURCE}'>
            {''.join(dependencies)}
          </datasource-dependencies>
          <aggregation value='true' />
        </view>
        <style>
          <style-rule element='axis'><format attr='title-font-color' value='#42526E' /></style-rule>
          <style-rule element='label'><format attr='font-color' value='#42526E' /></style-rule>
        </style>
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view><breakdown value='auto' /></view>
            <mark class='{mark}' />
            <encodings>
{encoding_xml}
            </encodings>
{style}
          </pane>
        </panes>
        <rows>{row_ref}</rows>
        <cols>{col_ref}</cols>
      </table>
      <simple-id uuid='{_uuid(name)}' />
    </worksheet>"""


def render_workbook(csv_path: Path) -> str:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []
    if not rows or not columns:
        raise ValueError("Tableau extract must contain headers and at least one row")

    types = {column: _tableau_type([row[column] for row in rows]) for column in columns}
    relation_columns = "\n".join(
        f"            <column datatype='{types[column]}' name='{escape(column)}' ordinal='{index}' />"
        for index, column in enumerate(columns)
    )
    metadata = "\n".join(
        f"""          <metadata-record class='column'>
            <remote-name>{escape(column)}</remote-name><remote-type>129</remote-type>
            <local-name>[{escape(column)}]</local-name><parent-name>[{DATA_FILE_NAME}]</parent-name>
            <remote-alias>{escape(column)}</remote-alias><ordinal>{index}</ordinal>
            <local-type>{types[column]}</local-type><aggregation>{'Count' if types[column] in {'string', 'boolean'} else ('Year' if types[column] in {'date', 'datetime'} else 'Sum')}</aggregation>
            <contains-null>true</contains-null>
          </metadata-record>"""
        for index, column in enumerate(columns)
    )

    landscape = _worksheet(
        "Repository Landscape",
        "Popularity vs. Maintenance Recency",
        [("stars", types["stars"]), ("days_since_last_push", types["days_since_last_push"]),
         ("forks", types["forks"]), ("maintenance_risk", types["maintenance_risk"]),
         ("repo_full_name", types["repo_full_name"])],
        "days_since_last_push",
        "stars",
        "Circle",
        [("color", "maintenance_risk"), ("size", "forks"), ("lod", "repo_full_name")],
        [("mark-labels-show", "false"), ("color", "#2684FF")],
    )
    ranking = _worksheet(
        "Evaluation Ranking",
        "Repository Evaluation Score",
        [("repo_full_name", types["repo_full_name"]), ("evaluation_score", types["evaluation_score"]),
         ("maintenance_risk", types["maintenance_risk"])],
        "repo_full_name",
        "evaluation_score",
        "Bar",
        [("color", "maintenance_risk"), ("text", "evaluation_score")],
        [("mark-labels-show", "true"), ("mark-labels-cull", "true")],
    )
    risk = _worksheet(
        "Maintenance Risk",
        "Repository Count by Maintenance Risk",
        [("maintenance_risk", types["maintenance_risk"]), ("Number of Records", "integer")],
        "maintenance_risk",
        "Number of Records",
        "Bar",
        [("color", "maintenance_risk"), ("text", "Number of Records")],
        [("mark-labels-show", "true"), ("mark-labels-cull", "false")],
    )

    return f"""<?xml version='1.0' encoding='utf-8'?>
<workbook source-build='2024.1.0' source-platform='win' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <SheetIdentifierTracking /><WindowsPersistSimpleIdentifiers /><ZoneFriendlyName />
  </document-format-change-manifest>
  <preferences><preference name='ui.encoding.shelf.height' value='24' /></preferences>
  <datasources>
    <datasource caption='Open-Source Ecosystem Intelligence' inline='true' name='{DATASOURCE}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='Governed repository momentum extract' name='textscan.ecosystem_extract'>
            <connection class='textscan' directory='Data' filename='{DATA_FILE_NAME}' password='' server='' />
          </named-connection>
        </named-connections>
        <relation connection='textscan.ecosystem_extract' name='{DATA_FILE_NAME}' table='[tableau_repo_momentum_extract#csv]' type='table'>
          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>
{relation_columns}
          </columns>
        </relation>
        <metadata-records>
{metadata}
        </metadata-records>
      </connection>
      <aliases enabled='yes' />
    </datasource>
  </datasources>
  <worksheets>
{landscape}
{ranking}
{risk}
  </worksheets>
  <dashboards>
    <dashboard name='Executive Overview'>
      <layout-options><title><formatted-text><run fontcolor='#172B4D' fontsize='22' bold='true'>Open-Source Ecosystem Intelligence</run></formatted-text></title></layout-options>
      <style><style-rule element='dashboard'><format attr='background-color' value='#F4F5F7' /></style-rule></style>
      <size maxheight='900' maxwidth='1400' minheight='900' minwidth='1400' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
          <zone h='60000' id='2' name='Repository Landscape' w='65000' x='1000' y='1000'><zone-style><format attr='margin' value='8' /></zone-style></zone>
          <zone h='60000' id='3' name='Evaluation Ranking' w='33000' x='66000' y='1000'><zone-style><format attr='margin' value='8' /></zone-style></zone>
          <zone h='37000' id='4' name='Maintenance Risk' w='98000' x='1000' y='62000'><zone-style><format attr='margin' value='8' /></zone-style></zone>
          <zone-style><format attr='margin' value='8' /></zone-style>
        </zone>
      </zones>
      <simple-id uuid='{_uuid('Executive Overview')}' />
    </dashboard>
  </dashboards>
  <windows saved-dpi-scale-factor='1'>
    <window class='dashboard' maximized='true' name='Executive Overview'>
      <viewpoints><viewpoint name='Repository Landscape' /><viewpoint name='Evaluation Ranking' /><viewpoint name='Maintenance Risk' /></viewpoints>
      <active id='2' /><simple-id uuid='{_uuid('dashboard-window')}' />
    </window>
  </windows>
</workbook>
"""


def build_tableau_package(csv_path: Path, workbook_path: Path, package_path: Path) -> None:
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_xml = render_workbook(csv_path)
    ElementTree.fromstring(workbook_xml)
    workbook_path.write_text(workbook_xml, encoding="utf-8")

    def deterministic_entry(name: str) -> zipfile.ZipInfo:
        entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o644 << 16
        return entry

    with zipfile.ZipFile(package_path, "w") as package:
        workbook_bytes = workbook_path.read_bytes()
        data_bytes = csv_path.read_bytes()
        package.writestr(deterministic_entry(WORKBOOK_NAME), workbook_bytes)
        package.writestr(deterministic_entry(f"Data/{DATA_FILE_NAME}"), data_bytes)

    with zipfile.ZipFile(package_path) as package:
        if package.testzip() is not None:
            raise ValueError("Generated Tableau package failed ZIP integrity validation")


def default_paths(root: Path) -> tuple[Path, Path, Path]:
    return (
        root / "outputs" / "analytics" / DATA_FILE_NAME,
        root / "tableau" / WORKBOOK_NAME,
        root / "outputs" / "dashboard" / PACKAGE_NAME,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    csv_path, workbook_path, package_path = default_paths(root)
    build_tableau_package(csv_path, workbook_path, package_path)
    print(f"Built {package_path.relative_to(root)}")


if __name__ == "__main__":
    main()
