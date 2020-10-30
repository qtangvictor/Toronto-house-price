# Toronto_house_price_prediction
An end-to-end machine learning project to predict house price in Toronto.
- 1)data scraping  and ETL locally as the file in notebooks folder shows.<br>
(if the jupyter notebook can not be opened, copy the jupyter notebook page address to https://nbviewer.jupyter.org/)
- 2)After doing ETL locally, upload train.csv,validation.csv,test.csv(like the files in training data for aws folder) to AWS s3. 
- 3)Training models in AWS sagemaker with the code in training-model-in-aws.ipynb and deploy the model as endpoint.
- 4)After deployment, build a lambda function deployment package that can invoke endpoint (see lambda function folder).
- 5)build a AWS API gateway that can receive API calls from web app and can trigger lambda function that created above.Then we can make post request to AWS sagemaker endpoint to get inference.
- 6)build a web app to enable real time house price prediction, as index.html shows.