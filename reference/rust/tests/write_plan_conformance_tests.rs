mod support;

use anyhow::Result;
use patch_guard::{
    DecodedInstruction, ExpectedWrite, ImageRegion, MachineCodeCheck, MachineCodeProvenance,
    MachineCodeVerifier, MachineCodeVerifierError, RegionKind, WriteIntent, WritePlan,
};
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    baseline: Vec<u8>,
    regions: Vec<Region>,
    writes: Vec<Write>,
    verifier: Option<Verifier>,
    audit_output: Option<Vec<u8>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Region {
    id: String,
    start: usize,
    end: usize,
    kind: Kind,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum Kind {
    Data,
    MachineCode,
    Protected,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Write {
    id: String,
    owner: String,
    offset: usize,
    expected_original: Vec<u8>,
    replacement: Vec<u8>,
    intent: Intent,
    assembly_source_id: Option<String>,
    isa_profile_id: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum Intent {
    Data,
    MachineCode,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Verifier {
    assembly_source_id: String,
    isa_profile_id: String,
    assembled: Vec<u8>,
    decoded: Vec<Instruction>,
    reassembled: Vec<u8>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Instruction {
    offset: usize,
    len: usize,
    canonical: String,
}

// These are declared verifier responses, not an implementation of a real ISA.
impl MachineCodeVerifier for Verifier {
    fn assemble_source(
        &self,
        check: &MachineCodeCheck<'_>,
    ) -> std::result::Result<Vec<u8>, MachineCodeVerifierError> {
        if check.provenance.assembly_source_id != self.assembly_source_id
            || check.provenance.isa_profile_id != self.isa_profile_id
        {
            return Err(MachineCodeVerifierError::new("fixture provenance mismatch"));
        }
        Ok(self.assembled.clone())
    }

    fn disassemble(
        &self,
        _check: &MachineCodeCheck<'_>,
    ) -> std::result::Result<Vec<DecodedInstruction>, MachineCodeVerifierError> {
        Ok(self
            .decoded
            .iter()
            .map(|i| DecodedInstruction {
                offset: i.offset,
                len: i.len,
                canonical: i.canonical.clone(),
            })
            .collect())
    }

    fn assemble_decoded(
        &self,
        _check: &MachineCodeCheck<'_>,
        instructions: &[DecodedInstruction],
    ) -> std::result::Result<Vec<u8>, MachineCodeVerifierError> {
        assert_eq!(
            instructions.len(),
            self.decoded.len(),
            "fixture decode changed"
        );
        for (actual, expected) in instructions.iter().zip(&self.decoded) {
            assert_eq!(
                (actual.offset, actual.len, &actual.canonical),
                (expected.offset, expected.len, &expected.canonical)
            );
        }
        Ok(self.reassembled.clone())
    }
}

#[test]
fn write_plan_cases_match_language_neutral_expectations() {
    support::run_manifest("write-plan.json", run);
}

fn run(input: Input) -> Result<Vec<u8>> {
    let plan = WritePlan {
        regions: input
            .regions
            .into_iter()
            .map(|r| ImageRegion {
                id: r.id,
                range: r.start..r.end,
                kind: match r.kind {
                    Kind::Data => RegionKind::Data,
                    Kind::MachineCode => RegionKind::MachineCode,
                    Kind::Protected => RegionKind::Protected,
                },
                reason: "conformance fixture".to_owned(),
            })
            .collect(),
        writes: input
            .writes
            .into_iter()
            .map(|w| ExpectedWrite {
                id: w.id,
                owner: w.owner,
                purpose: "conformance fixture".to_owned(),
                offset: w.offset,
                expected_original: w.expected_original,
                replacement: w.replacement,
                intent: match w.intent {
                    Intent::Data => WriteIntent::Data,
                    Intent::MachineCode => WriteIntent::MachineCode(MachineCodeProvenance {
                        assembly_source_id: w.assembly_source_id.expect("fixture assembly source"),
                        isa_profile_id: w.isa_profile_id.expect("fixture ISA profile"),
                    }),
                },
            })
            .collect(),
        ..WritePlan::default()
    };
    let verifier = input
        .verifier
        .as_ref()
        .map(|v| v as &dyn MachineCodeVerifier);
    let output = plan.apply(&input.baseline, verifier)?;
    plan.audit(
        &input.baseline,
        input.audit_output.as_deref().unwrap_or(&output),
        verifier,
    )?;
    Ok(output)
}
