from datetime import datetime
from io import StringIO
import requests
import json
import pandas as pd

def PullReachTimeseries(reachid):

    tend=datetime.utcnow()
    tend.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    baseurl= 'https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries?'
    time='&start_time=2022-12-01T00:00:00Z&end_time='+tend.strftime('%Y-%m-%dT%H:%M:%SZ')+'&'
    dataformat='csv'
    fieldstrs='time_str,wse,reach_q,p_lon,p_lat'
    url=baseurl + 'feature=Reach&feature_id=' +  reachid + time + 'output=' + dataformat + '&fields=' + fieldstrs

    # pull data from HydroChron into res variable
    print('waiting for SWOT data to download...')
    res = requests.get(url)
    
    # load data into a dictionary
    data=json.loads(res.text)
    
    # check that it worked
    if 'error' in data.keys():
        print('Error pulling data:',data['error'])
    elif data['status']=='200 OK':
        print('... done. Successfully pulled SWOT data and put in dictionary')
    else:
        print('Something went wrong: data not pulled or not stashed in dictionary correctly')
        
    # turn SWOT reslts into dataframe
    df=pd.read_csv(StringIO(data['results']['csv']))
    
    # filter SWOT results
    NODATA=-999999999999.0
    df=df[(df['wse']!=NODATA) & (df['reach_q']<2)]
    
    return df

def PullLongitudinalProfile(reachid,time):
    """
       1. Pull in all nodes for the reach using SWORD FTS
       2. Pull longprofile : WSE for each node in the reach using Hydrochron
    """
    
    # 1 Pull in all nodes for the reach using SWORD FTS
    nodeid_base=reachid[:-1]    
    response_multi = requests.get("https://fts.podaac.earthdata.nasa.gov/rivers/node/" + nodeid_base)
    nodeids=list(response_multi.json()['results'].keys())
    
    
    # 2. Pull long profile
    dfs=[]
    timestr='&start_time=' +time+ 'T00:00:00Z&end_time=' +time+ 'T23:59:59Z&'
    dataformat='geojson' #should switch this to csv 
    baseurl= 'https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries?'
    fields=['time_str','wse','p_dist_out']
    fieldstrs=''
    for field in fields:
        if fieldstrs:
            fieldstrs+=','+field
        else:
            fieldstrs=field

    print('pulling SWOT node data. this takes about 60 seconds...')
    for nodeid in nodeids:
        url=baseurl + 'feature=Node&feature_id=' +  nodeid + timestr + 'output=' + dataformat + '&fields=' + fieldstrs
        res = requests.get(url)
        data=json.loads(res.text)

        # check that it worked
        if 'error' in data.keys():
            print(nodeid,'  failed!')
            continue
        df=getdf(data,fields)
        dfs.append(df)    
    dfall=pd.concat(dfs)
    print('... done!')

    NODATA=-999999999999.0
    dfall=dfall[dfall['wse']!=NODATA]
    
    return dfall

def getdf(data,fields):
    df=pd.DataFrame(columns=fields)
    for feature in data['results']['geojson']['features']:
        data_els=feature['properties']

        rowdata=[]
        for field in fields:
            if field == 'slope' or field=='p_dist_out' or field=='wse':
                datafield=float(data_els[field])
            else:
                datafield=data_els[field]

            rowdata.append(datafield)

        df.loc[len(df.index)]=rowdata

    return df
