import * as cdk from 'aws-cdk-lib';
import {Duration, RemovalPolicy, Tags} from 'aws-cdk-lib';
import * as api from 'aws-cdk-lib/aws-apigatewayv2';
import * as integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as db from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as path from 'path';
import {Construct} from 'constructs';
export class ServiceDeskStack extends cdk.Stack {
 constructor(scope:Construct,id:string,props?:cdk.StackProps){super(scope,id,props);
  for(const [k,v] of Object.entries({Project:'portfolio',Environment:'demo',Owner:'caleo',AutoDestroy:'true'})) Tags.of(this).add(k,v);
  const options={partitionKey:{name:'id',type:db.AttributeType.STRING},billingMode:db.BillingMode.PAY_PER_REQUEST,removalPolicy:RemovalPolicy.DESTROY,timeToLiveAttribute:'expiresAt'};
  const tickets=new db.Table(this,'Tickets',options); const sessions=new db.Table(this,'Sessions',options); const catalog=new db.Table(this,'Catalog',{partitionKey:{name:'id',type:db.AttributeType.STRING},billingMode:db.BillingMode.PAY_PER_REQUEST,removalPolicy:RemovalPolicy.DESTROY});
  const logGroup=new logs.LogGroup(this,'AgentLogs',{retention:logs.RetentionDays.ONE_DAY,removalPolicy:RemovalPolicy.DESTROY});
  const fn=new lambda.Function(this,'Agent',{runtime:lambda.Runtime.PYTHON_3_12,handler:'index.handler',timeout:Duration.seconds(30),memorySize:1024,logGroup,environment:{TICKETS_TABLE:tickets.tableName,SESSIONS_TABLE:sessions.tableName,CATALOG_TABLE:catalog.tableName,BEDROCK_MODEL_ID:'us.amazon.nova-2-lite-v1:0'},code:lambda.Code.fromAsset(path.resolve(__dirname,'../../../services/lambda'))});
  tickets.grantReadWriteData(fn);sessions.grantReadWriteData(fn);catalog.grantReadData(fn);fn.addToRolePolicy(new cdk.aws_iam.PolicyStatement({actions:['bedrock:InvokeModel'],resources:['*']}));
  const http=new api.HttpApi(this,'DemoApi',{corsPreflight:{allowOrigins:['http://localhost:3100'],allowMethods:[api.CorsHttpMethod.POST]}});http.addRoutes({path:'/message',methods:[api.HttpMethod.POST],integration:new integrations.HttpLambdaIntegration('AgentIntegration',fn)});
  new cdk.CfnOutput(this,'ApiUrl',{value:http.apiEndpoint});new cdk.CfnOutput(this,'CatalogTable',{value:catalog.tableName});
 }
}
