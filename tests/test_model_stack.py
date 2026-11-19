"""Pin the nightly model build's stack (docs/nightly-model.md, sections 3, 4, 5, 7 and 8).

cfn-lint checks that model-stack/template.yaml is valid; it does not catch a size, a retry count or a permission
quietly changed, so the design's settings are asserted here, with the layer's DuckDB pin, the folder's own
samconfig.toml and the collector's requirements, which must never gain DuckDB.
"""
import tomllib
from pathlib import Path

import pytest
from cfnlint.decode import decode

ROOT = Path(__file__).parent.parent
STACK = ROOT / "model-stack"
TEMPLATE = STACK / "template.yaml"

ARCHIVE_READS = {"s3:GetObject", "s3:ListBucket"}
# The design's table (section 5): Sid -> (Action, Resource, Condition).
PERMISSIONS = {
    "ReadTheArchive": (
        "s3:GetObject",
        [{"Fn::Sub": "arn:aws:s3:::${ArchiveBucketName}/raw/*"},
         {"Fn::Sub": "arn:aws:s3:::${ArchiveBucketName}/receipts/*"}],
        None),
    "ListTheArchiveUnderRawAndReceipts": (
        "s3:ListBucket",
        {"Fn::Sub": "arn:aws:s3:::${ArchiveBucketName}"},
        {"StringLike": {"s3:prefix": ["raw/*", "receipts/*"]}}),
    "WriteBuildsAndThePointer": (
        "s3:PutObject",
        [{"Fn::Sub": "${ModelBucket.Arn}/models/*"}, {"Fn::Sub": "${ModelBucket.Arn}/latest.json"}],
        None),
    "DeleteOldBuilds": ("s3:DeleteObject", {"Fn::Sub": "${ModelBucket.Arn}/models/*"}, None),
    "ReadThePointer": ("s3:GetObject", {"Fn::Sub": "${ModelBucket.Arn}/latest.json"}, None),
    "ListTheModelBucket": ("s3:ListBucket", {"Fn::GetAtt": ["ModelBucket", "Arn"]}, None),
}


@pytest.fixture(scope="module")
def template():
    body, matches = decode(str(TEMPLATE))
    assert not matches, matches
    return body


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


@pytest.fixture(scope="module")
def function(resources):
    return resources["ModelFunction"]["Properties"]


@pytest.fixture(scope="module")
def statements(function):
    [policy] = function["Policies"]
    return policy["Statement"]


def listed(value):
    return value if isinstance(value, list) else [value]


def actions(statement):
    return set(listed(statement["Action"]))


def resource_texts(statement):
    """Each resource as text: a !Sub's string, a !GetAtt as ${Name.Attribute}, anything else as it prints."""
    texts = []
    for resource in listed(statement["Resource"]):
        if isinstance(resource, str):
            texts.append(resource)
        elif "Fn::Sub" in resource:
            texts.append(resource["Fn::Sub"] if isinstance(resource["Fn::Sub"], str) else resource["Fn::Sub"][0])
        elif "Fn::GetAtt" in resource:
            texts.append("${" + ".".join(resource["Fn::GetAtt"]) + "}")
        else:
            texts.append(repr(resource))
    return texts


def names_the_archive(statement):
    """A statement reaches the archive when a resource names its bucket, or is a wildcard over every bucket."""
    return any("ArchiveBucketName" in text or text == "*" or text.startswith("arn:aws:s3:::*")
               for text in resource_texts(statement))


def duckdb_pins(path):
    return [line.strip() for line in path.read_text().splitlines() if "duckdb" in line.lower()]


def test_only_the_four_expected_resources(template, resources):
    assert template["Transform"] == "AWS::Serverless-2016-10-31"
    assert "docs/nightly-model.md" in template["Description"]
    assert {name: r["Type"] for name, r in resources.items()} == {
        "ModelBucket": "AWS::S3::Bucket",
        "DuckDBLayer": "AWS::Serverless::LayerVersion",
        "ModelFunction": "AWS::Serverless::Function",
        "ModelLogs": "AWS::Logs::LogGroup",
    }


def test_no_retries_and_a_short_event_age(function):
    """A build that failed fails again the same way: the next night is the retry. A throttled or late copy of a
    night's event is dropped within the minute, not run as a second build hours later."""
    assert function["EventInvokeConfig"] == {"MaximumRetryAttempts": 0, "MaximumEventAgeInSeconds": 60}
    assert function["Events"]["Nightly"]["Properties"]["RetryPolicy"] == {"MaximumRetryAttempts": 0}


def test_runs_daily_at_01_40_utc(function):
    """01:40 UTC: ten minutes after the 01:30 board is stored with its receipt (section 8)."""
    assert list(function["Events"]) == ["Nightly"]
    event = function["Events"]["Nightly"]
    assert event["Type"] == "ScheduleV2"
    assert event["Properties"]["ScheduleExpression"] == "cron(40 1 * * ? *)"
    assert "ScheduleExpressionTimezone" not in event["Properties"]


def test_the_schedule_starts_switched_off(template, function):
    param = template["Parameters"]["ScheduleState"]
    assert param["Default"] == "DISABLED" and sorted(param["AllowedValues"]) == ["DISABLED", "ENABLED"]
    assert function["Events"]["Nightly"]["Properties"]["State"] == {"Ref": "ScheduleState"}


def test_the_sizes(function):
    """Section 3's table: 3,008 MB, the most /tmp and the longest run Lambda gives, on arm64."""
    assert function["MemorySize"] == 3008
    assert function["EphemeralStorage"] == {"Size": 10240}
    assert function["Timeout"] == 900
    assert function["Architectures"] == ["arm64"]
    assert function["Runtime"] == "python3.13"
    assert function["Handler"] == "nightly.handler.handler"
    assert function["CodeUri"] == "../src/"
    assert (STACK / function["CodeUri"]).resolve() == (ROOT / "src").resolve()


def test_the_runtime_changes_only_on_a_deploy(function):
    assert function["RuntimeManagementConfig"] == {"UpdateRuntimeOn": "FunctionUpdate"}


def test_logs_go_to_a_group_created_first(resources, function):
    assert function["LoggingConfig"]["LogGroup"] == {"Ref": "ModelLogs"}
    assert function["LoggingConfig"].get("LogFormat", "Text") == "Text"
    logs = resources["ModelLogs"]["Properties"]
    assert logs["LogGroupName"] == {"Fn::Sub": "/${AWS::StackName}/nightly"}
    assert logs["RetentionInDays"] == 30


def test_the_ping_address_is_a_secret(template, function):
    param = template["Parameters"]["HealthcheckUrl"]
    assert param["NoEcho"] is True
    assert param["MinLength"] == 20
    assert "Default" not in param  # given on the command line, never in a file
    assert function["Environment"]["Variables"]["HEALTHCHECK_URL"] == {"Ref": "HealthcheckUrl"}


def test_the_environment_names_both_buckets(template, function):
    """The archive bucket is a parameter, not an import from the collector's stack, which would tie the two."""
    assert set(template["Parameters"]) == {"ArchiveBucketName", "HealthcheckUrl", "ScheduleState"}
    assert template["Parameters"]["ArchiveBucketName"]["Type"] == "String"
    assert function["Environment"]["Variables"] == {
        "ARCHIVE_BUCKET": {"Ref": "ArchiveBucketName"},
        "MODEL_BUCKET": {"Ref": "ModelBucket"},
        "HEALTHCHECK_URL": {"Ref": "HealthcheckUrl"},
    }


def test_the_outputs_name_the_bucket_and_the_function(template):
    assert template["Outputs"] == {
        "ModelBucketName": {"Value": {"Ref": "ModelBucket"}},
        "ModelFunctionName": {"Value": {"Ref": "ModelFunction"}},
    }


def test_the_bucket_is_private_encrypted_and_unversioned(resources):
    """No versioning and no Object Lock: the model can always be rebuilt from the archive (section 4). Its one
    lifecycle rule ends unfinished uploads; old builds are deleted by the function, never by age."""
    props = resources["ModelBucket"]["Properties"]
    assert props["PublicAccessBlockConfiguration"] == {
        "BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True}
    assert props["OwnershipControls"] == {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}
    assert props["BucketEncryption"] == {
        "ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}
    assert props["LifecycleConfiguration"] == {"Rules": [{
        "Id": "end-unfinished-uploads",
        "Status": "Enabled",
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
    }]}
    assert "VersioningConfiguration" not in props
    assert "ObjectLockEnabled" not in props and "ObjectLockConfiguration" not in props
    assert set(props) == {"PublicAccessBlockConfiguration", "OwnershipControls", "BucketEncryption",
                          "LifecycleConfiguration"}


def test_the_layer_is_duckdb_for_python_3_13_on_arm64(resources, function):
    layer = resources["DuckDBLayer"]
    assert layer["Properties"]["ContentUri"] == "layer/"
    assert layer["Properties"]["CompatibleRuntimes"] == ["python3.13"]
    assert layer["Properties"]["CompatibleArchitectures"] == ["arm64"]
    assert layer["Metadata"] == {"BuildMethod": "python3.13", "BuildArchitecture": "arm64"}
    assert (STACK / layer["Properties"]["ContentUri"] / "requirements.txt").is_file()
    assert function["Layers"] == [{"Ref": "DuckDBLayer"}]


def test_the_permissions_are_the_designs(function, statements):
    [policy] = function["Policies"]
    assert set(policy) == {"Statement"}
    assert "Role" not in function  # a role of its own would replace these policies
    assert [s["Sid"] for s in statements] == list(PERMISSIONS)
    for statement in statements:
        action, resource, condition = PERMISSIONS[statement["Sid"]]
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == action, statement["Sid"]
        assert statement["Resource"] == resource, statement["Sid"]
        assert statement.get("Condition") == condition, statement["Sid"]
        assert set(statement) == {"Sid", "Effect", "Action", "Resource"} | ({"Condition"} if condition else set())


def test_archive_statements_only_read(statements):
    archive = [s for s in statements if names_the_archive(s)]
    assert archive, "the function must read the archive"
    for statement in archive:
        assert actions(statement) <= ARCHIVE_READS, statement["Sid"]


def test_listing_the_archive_is_held_to_raw_and_receipts(statements):
    [listing] = [s for s in statements if "s3:ListBucket" in actions(s) and names_the_archive(s)]
    assert listing["Condition"] == {"StringLike": {"s3:prefix": ["raw/*", "receipts/*"]}}


def test_nothing_may_delete_the_pointer(statements):
    """Every delete is under models/: not latest.json, not the bucket's root (/*), not *."""
    deletes = [s for s in statements if actions(s) & {"s3:DeleteObject", "s3:Delete*", "s3:*", "*"}]
    assert deletes, "the 30-day clean-up needs a delete"
    for statement in deletes:
        for text in resource_texts(statement):
            assert "latest.json" not in text, statement["Sid"]
            assert text.startswith("${ModelBucket.Arn}/models/"), (statement["Sid"], text)


def test_the_layer_pins_the_duckdb_that_ci_installs():
    dev = duckdb_pins(ROOT / "requirements-dev.txt")
    assert len(dev) == 1 and dev[0].startswith("duckdb==")
    layer = STACK / "layer" / "requirements.txt"
    assert [line.strip() for line in layer.read_text().splitlines() if line.strip()] == dev


def test_the_collectors_requirements_hold_no_duckdb():
    """DuckDB in src/requirements.txt would enter the collector's package too (section 7)."""
    assert duckdb_pins(ROOT / "src" / "requirements.txt") == []


def test_the_folders_samconfig_names_the_model_stack():
    """A bare sam command typed in model-stack/ follows this file: it must aim at the model's stack, in this
    project's region and profile, never the collector's."""
    config = tomllib.loads((STACK / "samconfig.toml").read_text())
    assert config == {
        "version": 0.1,
        "default": {
            "global": {"parameters": {
                "stack_name": "flights-archive-model", "region": "il-central-1", "profile": "flights-sam"}},
            "build": {"parameters": {"use_container": False}},
            "deploy": {"parameters": {
                "capabilities": "CAPABILITY_IAM", "confirm_changeset": True, "resolve_s3": True}},
        },
    }
    root = tomllib.loads((ROOT / "samconfig.toml").read_text())
    assert root["default"]["global"]["parameters"]["stack_name"] == "flights-archive"


def test_one_build_at_a_time(function):
    """Reserved concurrency 1, which the account check of 2026-11-20 allowed (docs/nightly-model-plan.md,
    "Deviations"). Two builds at once are harmless (section 4); this stops the second one anyway."""
    assert function["ReservedConcurrentExecutions"] == 1
