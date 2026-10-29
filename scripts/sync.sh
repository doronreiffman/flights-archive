#!/bin/sh
# Copy the archive into data/ for the model (read-only on AWS):
#   sh scripts/sync.sh
# Receipts first, then raw. The collector writes a receipt after its pages, so in this order every
# receipt that arrives finds its pages; the other order can bring a receipt without them.
set -eu
PROFILE=flights-sam
REGION=il-central-1
EXPECTED=arn:aws:iam::137953273942:user/doron-admin
BUCKET=flights-archive-archivebucket-onpwo5ns74tw

cd "$(dirname "$0")/.."
who=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text)
if [ "$who" != "$EXPECTED" ]; then
  echo "profile $PROFILE is $who, not $EXPECTED (account 137953273942); nothing synced" >&2
  exit 1
fi
aws s3 sync "s3://$BUCKET/receipts/" data/receipts/ --profile "$PROFILE" --region "$REGION"
aws s3 sync "s3://$BUCKET/raw/" data/raw/ --profile "$PROFILE" --region "$REGION"
