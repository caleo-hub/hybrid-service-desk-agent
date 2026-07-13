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
  const agentSource=path.resolve(__dirname,'../../../services/lambda');
  const runtimeArn='arn:aws:bedrock-agentcore:us-east-1:528049652959:runtime/HybridServiceDesk_ServiceDeskAgent-P1S7vg8eOH';
  const fn=new lambda.Function(this,'Agent',{runtime:lambda.Runtime.PYTHON_3_12,handler:'index.handler',timeout:Duration.seconds(45),memorySize:512,logGroup,environment:{AGENTCORE_RUNTIME_ARN:runtimeArn},code:lambda.Code.fromAsset(agentSource,{bundling:{image:lambda.Runtime.PYTHON_3_12.bundlingImage,command:['bash','-c','pip install -r requirements.txt -t /asset-output && cp -au . /asset-output']}})});
  fn.addToRolePolicy(new cdk.aws_iam.PolicyStatement({actions:['bedrock-agentcore:InvokeAgentRuntime'],resources:[runtimeArn,`${runtimeArn}/runtime-endpoint/*`]}));
  const http=new api.HttpApi(this,'DemoApi',{corsPreflight:{allowOrigins:['http://localhost:3100'],allowMethods:[api.CorsHttpMethod.POST]}});http.addRoutes({path:'/message',methods:[api.HttpMethod.POST],integration:new integrations.HttpLambdaIntegration('AgentIntegration',fn)});
  new cdk.CfnOutput(this,'ApiUrl',{value:http.apiEndpoint});new cdk.CfnOutput(this,'CatalogTable',{value:catalog.tableName});
 }
}
