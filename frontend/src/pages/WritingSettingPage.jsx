
import { useEffect, useRef, useState } from "react";
// CheckCircle2: 저장 완료 팝업에 쓰는 체크 아이콘
import { CheckCircle2 } from "lucide-react";
// 저장 완료 팝업 스타일 (화면 전체를 살짝 어둡게 덮고 가운데에 하얀 상자)
import "./WritingSettingPage.css";

const API_BASE_URL = "http://localhost:8000";

// 저장 완료 팝업을 보여준 뒤 글쓰기 화면으로 자동으로 돌아가기까지 기다리는 시간 (밀리초, 1500 = 1.5초)
const RETURN_DELAY = 1500;

const DEFAULT_SETTINGS = {
    preferred_tone: "natural",
    sentence_length: "normal",
    feedback_style: "detailed",
    ai_assistance: "balanced",
};

const SETTINGS_FIELDS = [
    {
        key: "preferred_tone",
        title: "선호하는 글쓰기 문체",
        options: [
            { value: "natural", label: "자연스럽고 부드럽게" },
            { value: "formal", label: "격식 있고 전문적으로" },
            { value: "confident", label: "자신감 있고 명확하게" },
        ],
    },
    {
        key: "sentence_length",
        title: "선호하는 문장 길이",
        options: [
            { value: "short", label: "짧고 간결하게" },
            { value: "normal", label: "적당한 길이로" },
            { value: "long", label: "자세하고 길게" },
        ],
    },
    {
        key: "feedback_style",
        title: "AI 피드백 방식",
        options: [
            { value: "brief", label: "핵심 내용만 간단히" },
            { value: "detailed", label: "이유와 개선 방법을 자세히" },
        ],
    },
    {
        key: "ai_assistance",
        title: "AI 글쓰기 지원 방식",
        options: [
            { value: "guided", label: "힌트와 방향 중심" },
            { value: "balanced", label: "힌트와 예시를 함께" },
            { value: "draft", label: "구체적인 초안 제안" },
        ],
    },
];

function WritingSettingPage({ auth, onBack }) {
    const [settings, setSettings] = useState(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState("");

    // showSavedPopup: "설정이 저장되었습니다" 팝업을 보여줄지 (true / false)
    const [showSavedPopup, setShowSavedPopup] = useState(false);
    // returnTimerRef: "1.5초 뒤 글쓰기 화면으로 돌아가기" 예약(setTimeout) 번호를 기억해 두는 곳
    // useRef 값은 바뀌어도 화면을 다시 그리지 않아서 타이머 번호 보관에 딱 맞음
    const returnTimerRef = useRef(null);

    // 화면을 떠날 때(뒤로가기 버튼 등) 남은 예약이 있으면 취소
    // → 다른 화면으로 이미 갔는데 1.5초 뒤에 글쓰기 화면으로 또 끌려가는 일을 막음
    useEffect(() => {
        return () => clearTimeout(returnTimerRef.current);
    }, []);

    // 팝업의 "바로 돌아가기" 버튼: 예약을 취소하고 지금 바로 글쓰기 화면으로
    const handleReturnNow = () => {
        clearTimeout(returnTimerRef.current);
        onBack();
    };

    // 로그인한 사용자의 설정 불러오기
    useEffect(() => {
        let cancelled = false;

        async function loadSettings() {
            if (!auth?.token) {
                setMessage("로그인이 필요한 기능입니다.");
                setLoading(false);
                return;
            }

            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/writing/preferences`,
                    {
                        headers: {
                            Authorization: `Bearer ${auth.token}`,
                        },
                    }
                );

                if (!response.ok) {
                    throw new Error("글쓰기 설정 조회에 실패했습니다.");
                }

                const data = await response.json();

                if (!cancelled) {
                    setSettings({
                        ...DEFAULT_SETTINGS,
                        ...data,
                    });
                }
            } catch (error) {
                if (!cancelled) {
                    setMessage(error.message);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        loadSettings();

        return () => {
            cancelled = true;
        };
    }, [auth?.token]);

    const handleChange = (key, value) => {
        setSettings((previous) => ({
            ...previous,
            [key]: value,
        }));
        setMessage("");
    };

    const handleSave = async () => {
        if (!auth?.token) {
            setMessage("로그인이 필요합니다.");
            return;
        }

        setSaving(true);
        setMessage("");

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/writing/preferences`,
                {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${auth.token}`,
                    },
                    body: JSON.stringify(settings),
                }
            );

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(
                    typeof errorData.detail === "string"
                        ? errorData.detail
                        : "설정 저장에 실패했습니다."
                );
            }

            // 저장 성공 → 팝업을 띄우고, 잠시 뒤 글쓰기 화면으로 자동으로 돌아감
            setShowSavedPopup(true);
            returnTimerRef.current = setTimeout(onBack, RETURN_DELAY);
        } catch (error) {
            setMessage(error.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div
            style={{
                maxWidth: "800px",
                margin: "0 auto",
                padding: "100px 24px 60px",
            }}
        >

            <button
                type="button"
                onClick={onBack}
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 16px",
                    marginBottom: "28px",
                    border: "1px solid #c9dced",
                    borderRadius: "8px",
                    backgroundColor: "#ffffff",
                    color: "#245780",
                    fontSize: "14px",
                    fontWeight: "500",
                    cursor: "pointer",
                }}
            >
                ← 글쓰기 화면으로 돌아가기
            </button>


            <h1 style={{ marginBottom: "10px" }}>
                나의 글쓰기 설정
            </h1>

            <p style={{ color: "#667085", marginBottom: "32px" }}>
                나에게 맞는 AI 글쓰기 스타일을 설정해 보세요.
                저장한 설정은 AI 초안 작성과 피드백에 활용됩니다.
            </p>

            {loading ? (
                <p>설정을 불러오는 중입니다...</p>
            ) : (
                <>
                    {SETTINGS_FIELDS.map((field) => (
                        <section
                            key={field.key}
                            style={{
                                padding: "24px",
                                marginBottom: "18px",
                                background: "#ffffff",
                                border: "1px solid #dbe7f3",
                                borderRadius: "12px",
                            }}
                        >
                            <h2
                                style={{
                                    fontSize: "18px",
                                    marginBottom: "18px",
                                }}
                            >
                                {field.title}
                            </h2>

                            {field.options.map((option) => (
                                <label
                                    key={option.value}
                                    style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "10px",
                                        padding: "9px 0",
                                        cursor: "pointer",
                                    }}
                                >
                                    <input
                                        type="radio"
                                        name={field.key}
                                        value={option.value}
                                        checked={settings[field.key] === option.value}
                                        onChange={() =>
                                            handleChange(field.key, option.value)
                                        }
                                    />
                                    {option.label}
                                </label>
                            ))}
                        </section>
                    ))}

                    {message && (
                        <p role="status" style={{ marginBottom: "18px" }}>
                            {message}
                        </p>
                    )}

                    <button
                        type="button"
                        onClick={handleSave}
                        // 팝업이 떠 있는 동안에도 막아서 두 번 저장되지 않게
                        disabled={saving || showSavedPopup || !auth?.token}
                        style={{
                            width: "100%",
                            padding: "15px",
                            background: "#64b5f6",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "10px",
                            cursor: saving ? "wait" : "pointer",
                            fontWeight: "bold",
                        }}
                    >
                        {saving ? "저장 중..." : "설정 저장하기"}
                    </button>
                </>
            )}

            {/*
              ===== 저장 완료 팝업 =====
              role="dialog" + aria-modal: 화면 읽기 프로그램에 "팝업 창"이라고 알려줌
              aria-live="polite": 팝업이 뜨면 안의 문구를 바로 읽어 줌
            */}
            {showSavedPopup && (
                <div className="setting-popup-backdrop">
                    <div
                        className="setting-popup"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="setting-popup-title"
                        aria-live="polite"
                    >
                        <CheckCircle2 size={44} strokeWidth={1.8} className="setting-popup-icon" />
                        <p id="setting-popup-title" className="setting-popup-title">
                            설정이 저장되었습니다
                        </p>
                        <p className="setting-popup-desc">
                            잠시 후 글쓰기 화면으로 돌아가요.
                        </p>
                        {/* autoFocus: 팝업이 뜨면 이 버튼에 바로 커서가 가서 엔터만 눌러도 돌아감 */}
                        <button
                            type="button"
                            className="setting-popup-button"
                            onClick={handleReturnNow}
                            autoFocus
                        >
                            바로 돌아가기
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default WritingSettingPage;
