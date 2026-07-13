import * as cdk from 'aws-cdk-lib'; import { ServiceDeskStack } from '../lib/service-desk-stack';
const app=new cdk.App(); new ServiceDeskStack(app,'HybridServiceDeskDemo',{env:{account:process.env.CDK_DEFAULT_ACCOUNT,region:process.env.CDK_DEFAULT_REGION??'us-east-1'}});
