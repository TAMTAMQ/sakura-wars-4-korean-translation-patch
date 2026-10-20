mod support;

use anyhow::Result;
use patch_guard::verify_exact_roundtrip;
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    boundary_id: String,
    original: Vec<u8>,
    rebuilt: Vec<u8>,
}

#[test]
fn roundtrip_cases_match_language_neutral_expectations() {
    support::run_manifest("roundtrip.json", |input: Input| -> Result<Vec<u8>> {
        verify_exact_roundtrip(&input.boundary_id, &input.original, &input.rebuilt)?;
        Ok(input.rebuilt)
    });
}
