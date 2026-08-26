REGION_DEALERS = {
    "R1": ["CA1", "CA8", "CA3", "CA6", "CA4", "CA7", "CA9", "CA2", "CA5", "PTM6"],
    "R2": ["KDL1", "KHT3", "KSV5", "TAK2", "BTI6", "PKB4", "SVA7", "PMR5", "SVR4", "CPH2", "KRV5", "KTB1"],
    "R3": ["KSP3", "KPS7", "KSM1", "PNP6", "KPT2", "CUK7", "KKG3", "SRA5", "KTR4", "KTL6", "KCG4", "TPG2"],
    "R4": ["VVG1", "PUS5", "BTB1", "BVL6", "PLN4", "PPT3", "KRG7", "MRS5"],
    "R5": ["BMC2", "PPR8", "KTH2", "KTM8", "SRP1", "CHK6", "PUK7"],
    "R6": ["KCM1", "BTY8", "STT4", "TKM2", "MMT3"],
    "R7": ["KRT1", "SNL6", "STR3", "MDK2", "KSA5", "RTK4", "BKE7"],
    "R8": ["PVH3", "CKS1", "AVG4", "SMR5"],
}
ALL_DEALERS = [dealer for dealers in REGION_DEALERS.values() for dealer in dealers]
DEALER_REGION = {dealer: region for region, dealers in REGION_DEALERS.items() for dealer in dealers}
