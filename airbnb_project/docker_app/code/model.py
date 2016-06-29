# -*- coding: utf-8 -*-

from sklearn.cross_validation import train_test_split
from sklearn.random_projection import GaussianRandomProjection
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor

import pandas as pd
import numpy as np

def predict(inputFeatures):
    
    # Get the data
    data_path = "locations_price.csv"
    dat = pd.read_csv(data_path)
    
    # Prepare the data for the model
    data = pd.concat((dat['longitude'],dat['latitude']),axis=1)
    target = dat['price']
    feature_names = ["longitude",'latitude']

    # Split data into train and test
    X_train, X_test, y_train, y_test = train_test_split(data, target, test_size=0.33, random_state=42)

    # Constructing the decision tree regressor model
    dt = DecisionTreeRegressor(criterion='mse', min_samples_leaf=150, max_depth=20)
    dt.fit(X_train,y_train)
    
    predictedPrice = dt.predict(inputFeatures)
    
    return round(predictedPrice,2)
