/**
 * STT Audio Worklet Processor
 * ─────────────────────────────────────────────────────────────────
 * deprecated된 ScriptProcessorNode를 대체하는 AudioWorklet 프로세서입니다.
 *
 * 【왜 AudioWorklet인가?】
 *  ScriptProcessorNode는 메인 스레드에서 오디오를 처리하므로:
 *  - UI 렌더링, GC(가비지 컬렉션)와 경합하여 프레임 드롭 발생
 *  - 드롭된 프레임의 음성 데이터가 유실되어 STT 인식 정확도 저하
 *
 *  AudioWorkletNode는 별도의 오디오 렌더링 스레드에서 처리하므로:
 *  - 메인 스레드 부하와 무관하게 안정적인 오디오 처리 보장
 *  - 프레임 드롭 없이 모든 음성 데이터를 빠짐없이 캡처
 *
 * 【동작 방식】
 *  1. AudioWorklet 스레드에서 128 샘플씩 process() 호출 (≈ 2.67ms @48kHz)
 *  2. 내부 버퍼에 누적하여 4096 샘플 단위로 메인 스레드에 전송
 *     - 4096 샘플 = ScriptProcessor의 기존 버퍼 크기와 동일
 *     - 48kHz 기준 약 85.3ms 간격 → 실시간 STT에 적합한 지연 시간
 *  3. 메인 스레드에서 toPcm16k() 변환 후 WebSocket으로 Deepgram에 전송
 *
 * 【버퍼링 전략】
 *  AudioWorklet의 기본 프레임 크기는 128 샘플로 매우 작습니다.
 *  매 128 샘플마다 postMessage()를 호출하면 메시지 오버헤드가 과도하므로
 *  (48kHz ÷ 128 = 초당 375회), 4096 샘플로 누적 후 전송합니다.
 *  이렇게 하면 초당 약 11.7회로 메시지 빈도가 줄어 성능이 개선됩니다.
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor
 */
class SttProcessor extends AudioWorkletProcessor {
    constructor() {
        super();

        // ── 버퍼 설정 ──
        // 4096 샘플 단위로 메인 스레드에 전송 (ScriptProcessor의 bufferSize와 동일)
        this._bufferSize = 4096;
        this._buffer = new Float32Array(this._bufferSize);
        this._writeIndex = 0;

        // 메인 스레드에서 활성화/비활성화 제어
        // (면접 미시작, 마이크 비활성화, 서버 STT 미사용 시 처리 스킵)
        this._active = true;

        // 메인 스레드로부터의 제어 메시지 수신
        this.port.onmessage = (event) => {
            if (event.data && event.data.type === "SET_ACTIVE") {
                this._active = event.data.active;
            }
        };
    }

    /**
     * 오디오 렌더링 스레드에서 호출되는 핵심 처리 함수.
     *
     * @param inputs  - 입력 오디오 데이터 [inputIndex][channelIndex][sampleIndex]
     * @param outputs - 출력 오디오 데이터 (사용하지 않음 — 패스스루)
     * @returns true = 프로세서 유지, false = 프로세서 종료
     */
    process(inputs) {
        // 비활성 상태면 오디오 데이터를 버리지만 프로세서는 유지
        if (!this._active) return true;

        // inputs[0] = 첫 번째 입력, [0] = 첫 번째(mono) 채널
        const input = inputs[0];
        if (!input || !input[0]) return true;

        const channelData = input[0]; // Float32Array (128 샘플)

        // ── 내부 버퍼에 누적 ──
        // 128 샘플씩 들어오는 데이터를 4096 샘플까지 모읍니다.
        for (let i = 0; i < channelData.length; i++) {
            this._buffer[this._writeIndex++] = channelData[i];

            // 버퍼가 가득 차면 메인 스레드로 전송
            if (this._writeIndex >= this._bufferSize) {
                // 버퍼 복사본을 전송 (원본은 즉시 재사용하므로)
                // Float32Array를 transferable object로 전송하면 zero-copy지만,
                // 버퍼를 재사용해야 하므로 slice()로 복사본을 만듭니다.
                this.port.postMessage({
                    type: "AUDIO_DATA",
                    audioData: this._buffer.slice(0),
                });
                this._writeIndex = 0;
            }
        }

        // true 반환 = 프로세서를 계속 유지 (false 반환 시 GC 대상)
        return true;
    }
}

// AudioWorklet 글로벌 스코프에 프로세서 등록
// 이름 "stt-processor"는 메인 스레드에서 new AudioWorkletNode(ctx, "stt-processor")로 참조
registerProcessor("stt-processor", SttProcessor);
