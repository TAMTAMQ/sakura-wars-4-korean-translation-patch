use std::{fs, path::PathBuf};

use anyhow::Result;
use patch_guard::WritePlanError;
use serde::{Deserialize, de::DeserializeOwned};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Manifest<T> {
    schema_version: u32,
    cases: Vec<Case<T>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Case<T> {
    id: String,
    expected: Expected,
    given: String,
    input: T,
    output: Option<Vec<u8>>,
    rejection: Option<String>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum Expected {
    Accept,
    Reject,
}

pub fn run_manifest<T: DeserializeOwned>(name: &str, runner: fn(T) -> Result<Vec<u8>>) {
    // reference/ is the copy unit: rust/ and conformance/ are siblings.
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../conformance")
        .join(name);
    let bytes = fs::read(&path).unwrap_or_else(|error| panic!("read {}: {error}", path.display()));
    let manifest: Manifest<T> = serde_json::from_slice(&bytes)
        .unwrap_or_else(|error| panic!("parse {}: {error}", path.display()));
    assert_eq!(manifest.schema_version, 2, "unsupported manifest {name}");
    assert!(!manifest.cases.is_empty(), "empty manifest {name}");
    for case in manifest.cases {
        let result = runner(case.input);
        let actual = if result.is_ok() {
            Expected::Accept
        } else {
            Expected::Reject
        };
        assert_eq!(
            actual, case.expected,
            "{}: {}: {result:?}",
            case.id, case.given
        );
        if let Some(expected) = case.rejection {
            let error = result
                .as_ref()
                .expect_err("rejection requires a failed result");
            let error = error
                .downcast_ref::<WritePlanError>()
                .expect("write-plan rejection");
            let actual = match error {
                WritePlanError::OverlappingWrites { .. } => "overlapping_writes",
                WritePlanError::ProtectedRegionWrite { .. } => "protected_region",
                WritePlanError::OriginalBytesMismatch { .. } => "original_bytes",
                WritePlanError::UntrackedFinalDiff { .. } => "untracked_diff",
                WritePlanError::IntentRegionMismatch { .. } => "intent_region",
                WritePlanError::MachineCodeVerifierMissing { .. } => "missing_verifier",
                WritePlanError::DecodedInstructionGap { .. } => "decode_gap",
                WritePlanError::DecodedReassemblyMismatch { .. } => "reassembly",
                other => panic!("{}: unexpected rejection {other:?}", case.id),
            };
            assert_eq!(actual, expected, "{} rejection cause", case.id);
        }
        if let Some(expected) = case.output {
            assert_eq!(result.unwrap(), expected, "{} output", case.id);
        }
    }
}
