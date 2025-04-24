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
    fieldstrs='time_str,wse,reach_q,p_lon,p_lat,slope'
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
        print('... done. Successfully pulled SWOT data.')
    else:
        print('Something went wrong: data not pulled correctly')
        
    # turn SWOT reslts into dataframe
    df=pd.read_csv(StringIO(data['results']['csv']))
    
    # filter SWOT results
    NODATA=-999999999999.0
    df=df[(df['wse']!=NODATA) & (df['reach_q']<2)]
    
    return df

def PullLongitudinalProfile(reachid,times,node_q_max=1):
    """
       1. Pull in all nodes for the reach using SWORD FTS
       2. Pull longprofile : WSE for each node in the reach using Hydrochron
    """
    
    # 1 Pull in all nodes for the reach using SWORD FTS
    nodeid_base=reachid[:-1]    
    response_multi = requests.get("https://fts.podaac.earthdata.nasa.gov/rivers/node/" + nodeid_base)
    nodeids=list(response_multi.json()['results'].keys())
    
    
    # 2. Pull long profile
    if len(times)>2:
        print('Warning - only the first and last time in the list will be processed')
    
    # figure out start and end times
    times.sort()    
    dfs=[]
    timestr='&start_time=' +times[0]+ 'T00:00:00Z&end_time=' +times[-1]+ 'T23:59:59Z&'
    dataformat='geojson' #should switch this to csv 
    baseurl= 'https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries?'
    fields=['time_str','wse','p_dist_out','node_q','width']
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
    
    # keep just the first and last
    dfall['date']=dfall['time_str'].str[:10]
    dfall=dfall[(dfall['date']==times[0]) | (dfall['date']==times[-1])]


    NODATA=-999999999999.0
    dfall=dfall[dfall['wse']!=NODATA]
    
    # remove node data based on flag
    dfall=dfall[dfall['node_q'].astype(int)<=node_q_max]
    
    return dfall

def getdf(data,fields):
    df=pd.DataFrame(columns=fields)
    for feature in data['results']['geojson']['features']:
        data_els=feature['properties']

        rowdata=[]
        for field in fields:
            if field == 'slope' or field=='p_dist_out' or field=='wse' or field =='width':
                datafield=float(data_els[field])
            else:
                datafield=data_els[field]

            rowdata.append(datafield)

        df.loc[len(df.index)]=rowdata

    return df

def ChangeDatum(df):
    '''
        this function changes datum using the vdatum api. https://vdatum.noaa.gov/docs/services.html                
        
        this function is currently limited in functionality to go from 
        SWOT in EGM08 to NAVD88. Future versions can accommodate a wider degree of 
        flexibility.
 
        The input dataframe "df" must contain the latitude, longitude and water elevation data pulled from SWOT.
        The dataframe is used to compute:
            x ~ approximate longitude of location to compute adjusted vertical data
            y ~ approximate latitude of location to compute adjusted vertical data        
             zin ~ swot elevation measurement in EGM08 [meters]
     
        This function  returns a vertical offset [meters] (swot_offset), and a revised elevation [meters] (zout)
        
        the offset is defined:
            zout = zin + swot_offset
            
        to use the offset, add it to the input elevation in EGM08. this operation returns elevation 
        in NAVD88, but it can be modified by maniuplating the vdatum API URL below.
                
    '''
    
    # Extract representative x (longitude) and y (latitude) to use for vdatum api to convert vertical datum
    x = df.p_lon.unique().item()
    y = df.p_lat.unique().item()
    zin=df.iloc[0]['wse'] # first in series    
    
    vdatum_url = f"https://vdatum.noaa.gov/vdatumweb/api/convert?region=ak&s_x={x}&s_y={y}&s_z={zin}&s_v_unit=m&s_h_frame=WGS84_G1674&s_v_frame=EGM2008&s_v_geoid=egm2008&t_v_frame=NAVD88&t_v_geoid=geoid12b"
    
    res = requests.get(vdatum_url)
    data=json.loads(res.text)
    zout = float(data["t_z"])  
    
    swot_offset=zout-zin
    
    return swot_offset, zout

