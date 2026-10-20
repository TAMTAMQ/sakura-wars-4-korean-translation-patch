# retro-typed-isa 기계어 검증 어댑터

Rust 제품 빌드에서 기계어를 생성하거나 옮길 때 [retro-typed-isa](https://github.com/mcpads/retro-typed-isa)를 선택할 수 있다. Rust 참고 구현의 `expected-write`는 쓰기 계획과 최종 diff를 검증한다.

대상에서 확인한 CPU와 실행 상태에 필요한 프로필을 선택한다. typed assembly 원천의 조립·해석·재조립을 `MachineCodeVerifier`에 연결한다. 프로필이 제공하는 `ExpectedWriteVerifier`를 사용하거나 같은 인터페이스의 프로젝트 어댑터를 구현한다.

검증은 두 범위를 구분한다. ISA 프로필 검증은 명령 집합 구현을 다루고, 프로젝트 검증은 실제 삽입 주소·실행 상태·선택한 원천과 최종 `ExpectedWrite`의 일치를 다룬다. 다른 구현에서도 프로젝트가 채택한 기계어 검증 조건을 보존한다.
