# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aws-cdk-lib>=2.180.0",
#     "constructs>=10.0.0",
# ]
# ///
"""
GitHub OIDC → AWS IAM role for GitHub Actions CI/CD.

This is a bootstrap stack: deploy it manually ONCE before GitHub Actions
workflows can authenticate.

Deploy:
    npx cdk deploy --app "uv run infra/github-oidc-stack.py" --profile subq-sandbox

Destroy:
    npx cdk destroy --app "uv run infra/github-oidc-stack.py" --profile subq-sandbox
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

ACCOUNT_ID = "292783887127"
ENV = cdk.Environment(account=ACCOUNT_ID, region="us-west-2")
REPO = "mlops-club/auto-monitoring-hackathon"
OIDC_PROVIDER_ARN = f"arn:aws:iam::{ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"


class GitHubOidcStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # --- GitHub OIDC Identity Provider ---
        # The provider already exists in this account (shared resource).
        # Import it by ARN instead of creating a new one.
        oidc_provider_arn = OIDC_PROVIDER_ARN

        # --- IAM Role for GitHub Actions ---
        # NOTE: AdministratorAccess is intentionally broad for this hackathon.
        # For production, scope down to only the permissions CDK and Helm need.
        role = iam.Role(
            self,
            "GitHubActionsRole",
            role_name="GitHubActionsRole",
            assumed_by=iam.FederatedPrincipal(
                oidc_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": f"repo:{REPO}:*",
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

        # --- Outputs ---
        CfnOutput(self, "GitHubActionsRoleArn", value=role.role_arn)
        CfnOutput(self, "OidcProviderArn", value=oidc_provider_arn)


app = cdk.App()
GitHubOidcStack(app, "GitHubOidc", env=ENV)
app.synth()
