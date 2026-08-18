"""Annexure data models representing the final exported data structure."""

from pydantic import BaseModel, Field


class AnnexureRecord(BaseModel):
    """A strongly typed representation of the final engineering Annexure.
    
    This model contains cleanly typed raw values representing the 19 engineering parameters,
    with painting flattened into external and internal, resulting in 20 total columns.
    It deliberately does not contain ExtractionField objects, confidences, or internal metadata.
    """

    tag_no: str = Field(description="TAG NO.")
    description: str = Field(description="DESCRIPTION")
    ref_data_sheet: str = Field(description="Ref Data Sheet")
    design_code: str = Field(description="DESIGN CODE")
    moc: str = Field(description="MOC (Main Material)")
    qty: int = Field(description="QTY.")
    orientation: str = Field(description="VERT / HOR")
    vessel_id_mm: float = Field(description="VESSEL ID (mm)")
    vessel_tl_tl_length_mm: float = Field(description="VESSEL (TL-TL) LENGTH (mm)")
    shell_min_thk_mm: float = Field(description="SHELL MIN. THK. (mm)")
    head_min_thk_mm: float = Field(description="HEAD MIN. THK. (mm)")
    head_type: str = Field(description="HEAD TYPE")
    nozzle_type: str = Field(description="NOZZLE TYPE")
    impact_tested: str = Field(description="Impact Tested")
    rt: str = Field(description="RT (Radiography)")
    pwht: str = Field(description="PWHT")
    support_type: str = Field(description="TYPE OF SUPPORT")
    painting_external: str = Field(description="EXTERNAL PAINTING")
    painting_internal: str = Field(description="INTERNAL PAINTING")
    pickling_passivation: str = Field(default="N/A", description="Pickling & Passivation")
    weight_tons_each: float = Field(description="WT-Tons (Each) (Approx.)")
