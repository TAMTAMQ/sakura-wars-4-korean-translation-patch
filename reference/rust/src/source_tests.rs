use super::*;

#[test]
fn source_identity_requires_length_and_hash() {
    let bytes = b"self-authored fixture";
    let hash = "121cc04d5d3d88d347d8507c503fc5cb9464fc5f92f873e10a98810b96fe4430";
    let valid = SourceSpec {
        id: "fixture-v1",
        len: bytes.len(),
        sha256: hash,
    };
    assert_eq!(verify_source(valid, bytes).unwrap().sha256, hash);

    let mut changed = bytes.to_vec();
    changed[0] ^= 1;
    assert!(verify_source(valid, &changed).is_err());

    assert!(
        verify_source(
            SourceSpec {
                len: bytes.len() + 1,
                ..valid
            },
            bytes
        )
        .is_err()
    );
    assert!(
        verify_source(
            SourceSpec {
                sha256: "00",
                ..valid
            },
            bytes
        )
        .is_err()
    );
}
