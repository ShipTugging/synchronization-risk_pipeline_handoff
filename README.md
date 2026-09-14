# Girting AI — Downstream Handoff

이 폴더는 Tugboat Safety AI Prototype V1의 downstream Girting Risk AI 개발을 위한 handoff package입니다.

Upstream의 Camera → Vision → IMU → Synchronization 파이프라인은 검증 완료되었으며,
downstream 개발에서는 `synchronized.jsonl`을 canonical input으로 사용합니다.

---

## Package Contents

### 1. `README_DOWNSTREAM.md`

현재 문서입니다.

Downstream AI의 담당 범위, 입력 데이터 구조, towline geometry 및 girting risk 구현 시 지켜야 할 기본 계약과 검토 사항을 설명합니다.

구현을 시작하기 전에 이 문서를 먼저 확인하세요.

---

### 2. `synchronized.jsonl`

**Downstream AI의 canonical input입니다.**

20초 recording의 각 Camera frame에 대해 Vision 결과와 가장 가까운 IMU sample이 timestamp 기준으로 synchronization되어 있습니다.

각 record에는 다음 정보가 포함됩니다.

- `timestamp_ms`
- Vision
  - `towline_detected`
  - `confidence`
  - `mask_base64`
  - `mask_width`
  - `mask_height`
- IMU
  - accelerometer x/y/z
  - gyroscope x/y/z
  - roll/pitch/yaw
- Synchronization
  - `matched`
  - `time_delta_ms`
- Recording metadata
  - `sequence_id`

Vision mask는 PNG binary mask를 Base64 string으로 저장한 것입니다.

Downstream에서는 이 mask를 decode하여 towline geometry를 계산합니다.

이 파일에서 다음 feature는 아직 제공되지 않습니다.

- `towline_angle_deg`
- `sag_ratio`

위 feature들은 downstream 담당자가 mask와 simulator/camera coordinate convention을 검토한 후 계산합니다.

`curvature`는 현재 Prototype V1 범위에서 제외되어 있습니다.

---

### 3. `input.mp4`

**원본 Camera recording입니다.**

Recording specification:

- Duration: 20 s
- Resolution: 1280 × 720
- Frame rate: 24 FPS
- Frames: 480
- Timestamp range: 0 ≤ t < 20,000 ms

Towline geometry 결과를 실제 영상과 비교하기 위한 visual reference로 사용합니다.

예를 들어 특정 timestamp에서 계산된:

- towline centerline
- endpoints
- towline angle
- sag

등이 실제 영상의 towline과 일치하는지 확인할 때 사용합니다.

---

### 4. `vision_overlay.mp4`

**YOLO-Seg Vision 결과를 시각화한 영상입니다.**

원본 `camera.mp4`에 Vision segmentation 결과가 overlay되어 있습니다.

다음 사항을 빠르게 확인하는 용도로 사용합니다.

- YOLO가 실제 towline을 검출하고 있는지
- segmentation mask 위치가 적절한지
- geometry 계산 실패가 Vision failure 때문인지 downstream geometry algorithm 때문인지

이 영상은 downstream AI의 직접적인 입력이 아니라 **visual validation reference**입니다.

---

### 5. `integration_validation.json`

**Upstream integration validation 결과입니다.**

`camera.mp4` → Vision → IMU → Synchronization 전체 pipeline이 정상적으로 연결되었는지 검증한 결과를 포함합니다.

현재 recording의 주요 검증 결과:

- Vision frames: 480
- Vision detected frames: 480 / 480
- Vision mean confidence: 0.96037
- Vision processing device: MPS
- Vision effective processing FPS: 39.77
- IMU samples: 2,000
- IMU sampling interval: 10 ms
- Synchronized records: 480
- Matched records: 480 / 480
- Unmatched records: 0
- Mean absolute synchronization delta: 2.5 ms
- P95 absolute synchronization delta: 5 ms
- Maximum absolute synchronization delta: 5 ms
- Vision mask preservation mismatches: 0

따라서 현재 `synchronized.jsonl`은 downstream geometry/risk 개발을 위한 검증된 입력으로 사용합니다.

---

## Recording Information

| Item | Value |
|---|---:|
| Sequence ID | `recording-v1-001` |
| Duration | 20 s |
| Camera Resolution | 1280 × 720 |
| Camera FPS | 24 FPS |
| Camera Frames | 480 |
| IMU Rate | 100 Hz |
| IMU Samples | 2,000 |
| Timestamp Origin | 0 ms |
| Synchronized Frames | 480 / 480 |
| Maximum Sync Delta | 5 ms |
| Mask Preservation Mismatch | 0 |

Camera와 IMU는 동일한 deterministic simulation clock에서 생성되었습니다.

---

## Recommended Starting Point

Downstream 개발에서는 다음 순서로 진행하는 것을 권장합니다.

1. `README_DOWNSTREAM.md` 확인
2. `synchronized.jsonl`의 일부 record 구조 확인
3. `mask_base64` decode
4. binary towline mask visualization
5. `camera.mp4` 및 `vision_overlay.mp4`와 비교
6. simulator/camera/IMU coordinate convention 확인
7. towline centerline 및 endpoint 정의
8. `towline_angle_deg` 정의
9. `sag_ratio` 정의
10. 정의와 가정을 팀 내 공유
11. 전체 480 frames에 geometry extraction 적용
12. synchronized IMU와 결합하여 Girting Risk logic 개발

---

## Important

`synchronized.jsonl`의 `towline_detected == false`는 **SAFE를 의미하지 않습니다.**

Towline이 검출되지 않거나 geometry 계산이 불가능한 경우에는 해당 상태를 `UNKNOWN`, `UNAVAILABLE` 또는 이에 준하는 invalid state로 처리해야 합니다.

또한 `sag_ratio`는 image-space geometric feature이며 실제 towline tension(kN) 측정값이 아닙니다.

현재 Prototype V1에는 실제 girting accident ground-truth dataset이 없으므로, downstream의 Girting Risk output을 실제 사고 확률로 해석하지 않습니다.