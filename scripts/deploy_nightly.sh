#!/bin/sh
# Build and deploy the nightly model build's stack, flights-archive-model (docs/nightly-model.md, section 5):
#   sh scripts/deploy_nightly.sh            # the schedule left DISABLED
#   sh scripts/deploy_nightly.sh ENABLED    # the schedule switched on
# This writes to AWS: run it only on the owner's go, in a terminal window, not through the coding agent's ! prefix.
# It asks for the healthchecks.io ping address, reads it with echo off and never prints it; sam deploy then asks
# for confirmation before it applies the change set. Nothing is deployed unless every check passes.
#
# The collector's stack is two bare commands away: the root samconfig.toml names flights-archive, and the root
# .aws-sam/build is the collector's build folder. So this script works in model-stack/ only, names the template and
# the build folder on its sam build and the stack on its sam deploy, and refuses a model-stack/samconfig.toml that
# does not name the model's stack, since a sam command typed in that folder follows it.
set -eu
PROFILE=flights-sam
REGION=il-central-1
EXPECTED=arn:aws:iam::137953273942:user/doron-admin
STACK=flights-archive-model
ARCHIVE_BUCKET=flights-archive-archivebucket-onpwo5ns74tw

ROOT=$(cd "$(dirname "$0")/.." && pwd)
FOLDER=$ROOT/model-stack

# One argument at most, DISABLED (the default) or ENABLED: anything else, a stack name included, is refused.
case "$#:${1:-}" in
  0: | 1:DISABLED | 1:ENABLED) state=${1:-DISABLED} ;;
  *) echo "the only argument taken is DISABLED (the default) or ENABLED; nothing deployed" >&2; exit 1 ;;
esac
if ! grep -qsxF "stack_name = \"$STACK\"" "$FOLDER/samconfig.toml"; then
  echo "$FOLDER/samconfig.toml has no line stack_name = \"$STACK\"; nothing deployed" >&2
  exit 1
fi
who=$(aws sts get-caller-identity --profile "$PROFILE" --query Arn --output text)
if [ "$who" != "$EXPECTED" ]; then
  echo "profile $PROFILE is $who, not $EXPECTED (account 137953273942); nothing deployed" >&2
  exit 1
fi

# The address is the stack's secret parameter (NoEcho in model-stack/template.yaml). At a terminal, echo goes off
# before the prompt and comes back on after the line is read, before sam deploy asks for confirmation, or at any exit
# before that.
if [ -t 0 ]; then
  trap 'stty echo' EXIT
  trap 'exit 1' HUP INT TERM  # dash skips the EXIT trap when a signal ends it; bash, macOS's sh, runs it
  stty -echo
fi
printf 'healthchecks.io ping address for the model check: ' >&2
read -r url || true
if [ -t 0 ]; then
  stty echo
  echo >&2
fi
case "$url" in
  https://hc-ping.com/?*) ;;
  *) echo "the address is not an https address on hc-ping.com with a path; nothing deployed" >&2; exit 1 ;;
esac

cd "$FOLDER"
sam build --template-file template.yaml --build-dir .aws-sam/build
sam deploy --template-file .aws-sam/build/template.yaml --stack-name "$STACK" --profile "$PROFILE" --region "$REGION" \
  --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset \
  --parameter-overrides "ArchiveBucketName=$ARCHIVE_BUCKET" "HealthcheckUrl=$url" "ScheduleState=$state"
