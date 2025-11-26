from src.xbrl.concept_resolver import resolve

def test_revenue_aliases():
    assert resolve("RevenueFromContractWithCustomer") == "Revenue"
    assert resolve("us-gaap:TotalRevenue") == "Revenue"
    assert resolve("Revenues") == "Revenue"

def test_cogs_aliases():
    assert resolve("CostOfGoodsSold") == "CostOfRevenue"
    assert resolve("us-gaap:CostOfProductsSold") == "CostOfRevenue"

def test_ganda_aliases():
    assert resolve("SG&A") == "GandA"

def test_ppe_aliases():
    assert resolve("us-gaap:PropertyPlantAndEquipmentNet") == "PPE"

