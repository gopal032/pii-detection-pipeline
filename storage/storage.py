import pandas as pd
import json

def store_in_dataframe(texts):
    df = pd.DataFrame({"Page": range(1, len(texts)+1), "Text": texts})
    return df

def export_to_json(df, filename="output.json"):
    df.to_json(filename, orient="records")
    