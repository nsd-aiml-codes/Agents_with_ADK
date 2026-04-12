from fastmcp import FastMCP, Client
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import sqlite
from sqlalchemy import Table, MetaData, create_engine
from google.cloud.sql.connector import Connector
import sqlalchemy
from typing import List, Dict
# from pydantic import BaseModel, Field, validator
from typing import List, Dict
from decimal import Decimal
import os
import pandas as pd
from sqlalchemy import text
import json
from toon import encode, decode
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
from pydantic import BaseModel, Field, field_validator
mcp_server = FastMCP()
connector = Connector()

db_name = os.getenv('database_name')
username = os.getenv('username')
db_pass = os.getenv('db_passward')
connection_name = os.getenv('connection_name')

df = None
result = None

engine = create_engine(
    f"mysql+pymysql://{username}:{db_pass}.replace('@','%40')@172.23.0.1:3306/{db_name}"
)

@mcp_server.tool
def greeting_tool(name: str):
    """Generates a personalized greeting.
    Args:
        name: name of the person to greet
    returns: 
        A greeting string

    """
    return f"Hello {name}, Nice to meet you."


def get_sample_for_column(table_name):
    "Get sample data for each column in table"
    df = pd.read_sql(text(f"SELECT * from {table_name} LIMIT 10"), engine)
    return df


@mcp_server.tool
def get_sql_table_schema() -> dict:
    '''Get get schema of all tables present in database'''
  
    table_scahema = {}

    inspector = sqlalchemy.inspect(engine)
    try:
        for table_name in inspector.get_table_names():
            samples = get_sample_for_column(table_name)
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)

            table_scahema[table_name] = {
                'columns': [
                    {
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': str(col['default']) if col['default'] else None
                    }
                    for col in columns
                ],
                'primary_key': pk.get('constrained_columns', []),
                'foreign_keys': [
                    {
                        'columns': fk['constrained_columns'],
                        'referred_tables': fk['referred_table'],
                        'referred_columns': fk['referred_columns']
                    }
                    for fk in fks
                ]

            }
        return {'status': 'Success',
                'Error': None,
                'data': table_scahema
                }
    except Exception as e:
        return {'status': 'Fail',
                'Error': str(e),
                'data': None
                }



    
@mcp_server.tool
def validate_query(query: str) -> dict:
    """
    Validate Sql Query against databse without Fetching data.
    
    Args:
     query: Sql Query to check its valdity against database.
    
    Returns:

    """
    conn = engine.connect()

    try:
        sql_result = conn.execute(sqlalchemy.text(f"Explain {query}"))
        return {'status': 'SUCCESS', 'error': None, 'Query': query, 'result': sql_result}
    except Exception as e:
        return {'status': 'FAIL', 'error': str(e), 'Query': query, 'result': ''}



@mcp_server.tool
def get_sql_data(query: str) -> dict:
    """
    Executes a raw SQL query to fetch Information, staatistic of sql query data.

    Args:
        query: The complete SQL query string to execute.
    
    Returns:
        Data information, stats and uniqueness of each column as output
    """
    from decimal import Decimal
    import json

    global df
    global result
    try:

        with engine.connect() as conn:
            sql_result = conn.execute(sqlalchemy.text(query)).mappings().all()

        final_result = []
        for row in sql_result:
            processed_row = {}
            for k, v in row.items():
                if isinstance(v, Decimal):
                    processed_row[k] = float(v)
                else:
                    processed_row[k] = v
            final_result.append(processed_row)
        df = pd.read_json(json.dumps(final_result))
        
        result = df.count().to_frame("non_null").assign(dtype = df.dtypes.astype(str)).reset_index().rename(columns = {"index": "column"}).to_dict(orient = "records")
        result = {'info': result, 'description': df.describe().unstack(-1).unstack(0).to_dict(), 'uniquness': df.nunique(dropna = False).to_dict(), 'error': None}
        return result
    
    except Exception as e:
        return {'info':'', 'description':'', 'uniquness':'', 'error': str(e)}

@mcp_server.tool
def execute_graph(graph_code : str)-> str:
    """Validate plotly visualization code using python.
    Args:
        graph_code : Python code for Graph Generation.
    Returns:
        status: Success or Fail
        Error: Error while generating Plotly graphs
        data: actual data
    """
    global df, result

    graph_code = graph_code.strip()
    namespace = {'df': df}

    try:
        exec(graph_code, namespace)
        fig = namespace.get('fig')
    except Exception as e:
        return {'status': 'FAIL', 'Error': f'{e}', 'data': None}
    
    if "fig" not in namespace:
        return {'status': 'FAIL', 'Error': "fig not found in namespace", 'data': None}
    return {'status': 'SUCCESS', 'Error': None, 'data': fig}


if __name__=='__main__':
    mcp_server.run(transport = 'stdio')
