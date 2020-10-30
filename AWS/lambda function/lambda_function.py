import os
import io
import boto3
import json
import csv
import numpy as np
import pandas as pd
from shapely.geometry import Point,Polygon

runtime= boto3.client('runtime.sagemaker')
def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    data = json.loads(json.dumps(event))
    # encode categorical feature to number
    levels_map={'Apartment':1,'2-Storey':2,'Bungalow':3,'3-Storey':4,'Others':5,'Loft':6,'2+1/2 Storey':7,'1+1/2 Storey':8,'Stacked Townhouse':9,'Bungalow-Raised':10,'Multi-Level':11}
    locker_map={'missing':0,'Owned':1,'None':2,'Exclusive':3,'Ensuite':4,'Others':5} 
    exterior_map={'Brick':1,'Concrete':2,'Stucco':3,'Alum':4,'Brick and Concrete':5,'Brick and Stone':6,'Others':7,'Stone':8,'missing':0}
    basement_map={'None':1,'Finished':2,'Finished and Sep Entrance':3,'Unfinished':4,'Others':5,'missing':0}
    garage_map={'Underground':1,'None':2,'Detached':3,'Attached':4,'Built-In':5,'Carport':6,'Others':7,'Surface':8,'missing':0}
    driveway_map={'Private':1,'Lane':2,'Private Double':3,'Mutual':4,'None':5,'Others':6,'Front Yard':7,'missing':0}
    heat_map={'Forced Air':1,'Heat Pump':2,'Water':3,'Radiant':4,'Fan Coil':5,'Baseboard':6,'Others':7,'missing':0}
    ac_map={'Central Air':1,'None':2,'Wall Unit':3,'Window Unit':4,'Others':5,'missing':0}
    heatingFuel_map={'Gas':1,'Electric':2,'Others':3,'missing':0}
    styleName_map={'condo-highrise':1,'house-detached':2,'house-semidetached':3,'townhouse':4,'condo-lowrise':5,'house-attached':6,'condo-others':7}
    balcony_map={'Open':1,'None':2,'Terrace':3,'Juliette':4,'Enclosed':5,'missing':0}
    approxAge_map = {'0-5':1,'6-15':2,'16-30':3,'31-50':4,'51-99':5,'100+':6,'missing':0}
    fireplaceStove_map = {'Owned':1,'None':2,'missing':0}
    parkingType_map = {'missing':0,'Owned':1,'None':2,'Exclusive':3,'Rental':4,'Others':5}

    cols=['bedrooms', 'bathrooms', 'levels', 'locker', 'parking','maintenanceFees', 'taxes', 'exterior', 'basement', 'garage','driveway', 'heat', 'ac', 'heatingFuel', 'styleName', 'approxAge','balcony', 'fireplaceStove', 'kitchens', 'parkingType', 'stories','sqft_min', 'sqft_max', 'latitude', 'longitude']
    for col in cols:
        if type(data[col])==str:
            exec("data['"+col+"']="+col+"_map[data['"+col+"']]")
    payload=''
    for col in cols:
        payload = payload+str(data[col])+','

	# calculate the subway distance
    bucket = 'toronto-house-price-project'
    file_name = 'input/subway_stations.csv'
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket, file_name)
    subway = pd.read_csv(obj.get()['Body'])	
    subway_distance = float(shortest_distance(data['latitude'],data['longitude'],subway))
    payload = payload+str(subway_distance)+','

    # extract neighbourhood_id
    file_name = 'input/Neighbourhoods.geojson'
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket, file_name)
    geo_data = json.load(obj.get()['Body'])
    neighbourhood_id = find_neighbourhood(data['latitude'],data['longitude'],geo_data)
    if neighbourhood_id is not None:
        neighbourhood_id = int(neighbourhood_id)
    else:
        return {'msg':'The house seems not within Toronto!','price':None,"neighbourhood":None,"neighbourhood_price":None,'price_rank':None}
    payload = payload+str(neighbourhood_id)+','


    # extract neighbourhood income
    file_name = 'input/neighbourhood-profiles-2016-csv.csv'
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket, file_name)
    neighbourhood_data = pd.read_csv(obj.get()['Body']) 
    income = neighbourhood_data[(neighbourhood_data.Characteristic == 'Neighbourhood Number') | (neighbourhood_data.Characteristic == 'Total income: Average amount ($)')]
    df_income = pd.DataFrame({'neighbourhood_id':income.iloc[0,6:],'income':income.iloc[1,6:]})
    df_income.neighbourhood_id = df_income.neighbourhood_id.astype('int64') # convert id to int
    df_income.income = df_income.income.apply(lambda a: a.replace(',','')).astype('int64')# convert income to int
    income = int(df_income.loc[df_income['neighbourhood_id']==neighbourhood_id]['income'][0])
    payload = payload+str(income)
    print(payload)
    
    response = runtime.invoke_endpoint(EndpointName='endpoint-v1',ContentType='text/csv',Body=payload)
    result = json.loads(response['Body'].read().decode())
    print(result)
  
    
    # extract neighbourhood info from s3
    file_name = 'input/price_by_neighbourhood.csv'
    s3 = boto3.resource('s3')
    obj = s3.Object(bucket, file_name)
    neighbourhood_price = pd.read_csv(obj.get()['Body'])
    neighbourhood_name = neighbourhood_price[neighbourhood_price.neighbourhood_id==neighbourhood_id].iloc[0,0]
    avg_price = neighbourhood_price[neighbourhood_price.neighbourhood_id==neighbourhood_id].iloc[0,3]
    neighbourhood_rank = neighbourhood_price[neighbourhood_price.neighbourhood_id==neighbourhood_id].iloc[0,4]


    return {'msg':'Success','price':result,"neighbourhood":neighbourhood_name,"neighbourhood_price":str(avg_price),'price_rank':str(neighbourhood_rank)}



def shortest_distance(lat,lng,subway):
    subway_coor = subway[['latitude','longitude']]   
    shortest = float('inf')
    AVG_EARTH_RADIUS = 6371  # in km
    for row in range(subway_coor.shape[0]):
        lat1,lng1 = lat,lng
        lat2,lng2 = subway_coor.loc[row,:]
        lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))       
        lat3 = lat2 - lat1
        lng3 = lng2 - lng1
        d = np.sin(lat3 * 0.5) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(lng3 * 0.5) ** 2
        h = 2 * AVG_EARTH_RADIUS * np.arcsin(np.sqrt(d))                    
        shortest = min(shortest,h)
    return shortest

def find_neighbourhood(lat,lng,geodata):
    p = Point(lng,lat)
    for i in range(len(geodata['features'])): #iterate over 140 neighbourhoods
        poly = Polygon(geodata['features'][i]['geometry']['coordinates'][0])
        if p.within(poly):
            return geodata['features'][i]['properties']['AREA_SHORT_CODE']#return id 
    return None # if not within any neighbourhood, return None




  
