import { useState } from "react";

function Writing() {
  const [documentType, setDocumentType] = useState("자기소개서");
  const [title, setTitle] = useState("");
  const [documentId, setDocumentId] = useState(null);

  const [thought, setThought] = useState("");
  const [structure, setStructure] = useState(null);
  const [message, setMessage] = useState("");

  const [followUpAnswers, setFollowUpAnswers] = useState({
    situation: "",
    problem: "",
    action: "",
    result: "",
    meaning: "",
  });

  const [draft, setDraft] = useState("");
  const [drafts, setDrafts] = useState([]);

  const [leftDraftId, setLeftDraftId] = useState("");
  const [rightDraftId, setRightDraftId] = useState("");

  // 1. 문서 생성
  const createDocument = async () => {
    if (!title.trim()) {
      setMessage("제목을 입력해주세요.");
      return;
    }

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/documents",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            document_type: documentType,
            title: title,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("문서 생성 실패");
      }

      const data = await response.json();

      setDocumentId(data.id);
      setThought("");
      setStructure(null);
      setDraft("");
      setDrafts([]);
      setLeftDraftId("");
      setRightDraftId("");

      setFollowUpAnswers({
        situation: "",
        problem: "",
        action: "",
        result: "",
        meaning: "",
      });

      setMessage(
        `문서가 생성되었습니다. 문서 ID: ${data.id}`
      );
    } catch (error) {
      console.error(error);
      setMessage("문서 생성 중 오류가 발생했습니다.");
    }
  };

  // 2. 생각 저장
  const saveThought = async () => {
    if (!documentId) {
      setMessage("먼저 문서를 생성해주세요.");
      return;
    }

    if (!thought.trim()) {
      setMessage("생각을 입력해주세요.");
      return;
    }

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/thoughts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            document_id: documentId,
            content: thought,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("생각 저장 실패");
      }

      await response.json();

      setMessage("생각이 저장되었습니다.");
      setThought("");
    } catch (error) {
      console.error(error);
      setMessage("생각 저장 중 오류가 발생했습니다.");
    }
  };

  // 3. AI 구조화
  const createStructure = async () => {
    if (!documentId) {
      setMessage("먼저 문서를 생성해주세요.");
      return;
    }

    try {
      setMessage("AI가 생각을 구조화하고 있습니다...");

      const response = await fetch(
        `http://127.0.0.1:8000/api/documents/${documentId}/structure-ai`,
        {
          method: "POST",
        }
      );

      if (!response.ok) {
        const errorData = await response.json();

        throw new Error(
          errorData.detail || "AI 구조화 실패"
        );
      }

      const data = await response.json();

      setStructure(data.structure);

      setFollowUpAnswers({
        situation: "",
        problem: "",
        action: "",
        result: "",
        meaning: "",
      });

      setMessage("AI 구조화가 완료되었습니다.");
    } catch (error) {
      console.error(error);

      setMessage(
        error.message || "AI 구조화 중 오류가 발생했습니다."
      );
    }
  };

  // 4. 추가 질문 답변 반영
  const submitFollowUp = async () => {
    if (!documentId || !structure) {
      setMessage("먼저 AI 구조화를 진행해주세요.");
      return;
    }

    const answers = {};

    if (
      !structure.situation &&
      followUpAnswers.situation.trim()
    ) {
      answers.situation =
        followUpAnswers.situation.trim();
    }

    if (
      !structure.problem &&
      followUpAnswers.problem.trim()
    ) {
      answers.problem =
        followUpAnswers.problem.trim();
    }

    if (
      !structure.action &&
      followUpAnswers.action.trim()
    ) {
      answers.action =
        followUpAnswers.action.trim();
    }

    if (
      !structure.result &&
      followUpAnswers.result.trim()
    ) {
      answers.result =
        followUpAnswers.result.trim();
    }

    if (
      !structure.meaning &&
      followUpAnswers.meaning.trim()
    ) {
      answers.meaning =
        followUpAnswers.meaning.trim();
    }

    if (Object.keys(answers).length === 0) {
      setMessage("추가 답변을 입력해주세요.");
      return;
    }

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/documents/${documentId}/structure-followup`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(answers),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();

        throw new Error(
          errorData.detail || "추가 답변 반영 실패"
        );
      }

      const data = await response.json();

      setStructure(data.structure);

      setFollowUpAnswers({
        situation: "",
        problem: "",
        action: "",
        result: "",
        meaning: "",
      });

      setMessage(
        "추가 답변이 구조에 반영되었습니다."
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error.message ||
          "추가 답변 반영 중 오류가 발생했습니다."
      );
    }
  };

  // 5. 초안 저장
  const saveDraft = async () => {
    if (!documentId) {
      setMessage("먼저 문서를 생성해주세요.");
      return;
    }

    if (!draft.trim()) {
      setMessage("초안을 입력해주세요.");
      return;
    }

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/drafts",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            document_id: documentId,
            content: draft,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();

        throw new Error(
          errorData.detail || "초안 저장 실패"
        );
      }

      const data = await response.json();

      setMessage(
        `초안 버전 ${data.version}이 저장되었습니다.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error.message ||
          "초안 저장 중 오류가 발생했습니다."
      );
    }
  };

  // 6. 저장된 초안 불러오기
  const loadDrafts = async () => {
    if (!documentId) {
      setMessage("먼저 문서를 생성해주세요.");
      return;
    }

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/documents/${documentId}/drafts`
      );

      if (!response.ok) {
        throw new Error("초안 목록 불러오기 실패");
      }

      const data = await response.json();

      setDrafts(data);
      setMessage("저장된 초안을 불러왔습니다.");
    } catch (error) {
      console.error(error);

      setMessage(
        "초안 목록을 불러오는 중 오류가 발생했습니다."
      );
    }
  };

  const leftDraft = drafts.find(
    (item) =>
      item.id === Number(leftDraftId)
  );

  const rightDraft = drafts.find(
    (item) =>
      item.id === Number(rightDraftId)
  );

  const hasMissingStructure =
    structure &&
    (
      !structure.situation ||
      !structure.problem ||
      !structure.action ||
      !structure.result ||
      !structure.meaning
    );

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "40px auto",
        padding: "20px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <h1>생각한줄 글쓰기</h1>

      <p>
        글 종류와 제목을 정한 뒤 생각을 입력하고,
        AI가 글의 구조를 정리하도록 할 수 있습니다.
      </p>

      <hr />

      {/* 1. 문서 만들기 */}
      <h2>1. 문서 만들기</h2>

      <div>
        <label>
          글 종류

          <select
            value={documentType}
            onChange={(e) =>
              setDocumentType(e.target.value)
            }
            style={{
              marginLeft: "10px",
              padding: "8px",
            }}
          >
            <option value="자기소개서">
              자기소개서
            </option>

            <option value="보고서">
              보고서
            </option>
          </select>
        </label>
      </div>

      <div style={{ marginTop: "10px" }}>
        <label>
          제목

          <input
            type="text"
            value={title}
            onChange={(e) =>
              setTitle(e.target.value)
            }
            placeholder="예: 삼성전자 지원 자기소개서"
            style={{
              marginLeft: "10px",
              padding: "8px",
              width: "300px",
            }}
          />
        </label>
      </div>

      <button
        onClick={createDocument}
        style={{
          marginTop: "10px",
          padding: "10px 20px",
          cursor: "pointer",
        }}
      >
        문서 생성
      </button>

      {documentId && (
        <p>
          현재 문서 ID: {documentId}
        </p>
      )}

      <hr />

      {/* 2. 생각 입력 */}
      <h2>2. 생각 입력</h2>

      <textarea
        value={thought}
        onChange={(e) =>
          setThought(e.target.value)
        }
        placeholder="예: 카페 아르바이트를 시작했는데 처음에는 주문 실수가 많았다."
        rows="6"
        style={{
          width: "100%",
          padding: "12px",
          boxSizing: "border-box",
        }}
      />

      <div style={{ marginTop: "10px" }}>
        <button
          onClick={saveThought}
          style={{
            padding: "10px 20px",
            cursor: "pointer",
          }}
        >
          생각 저장
        </button>

        <button
          onClick={createStructure}
          style={{
            marginLeft: "10px",
            padding: "10px 20px",
            cursor: "pointer",
          }}
        >
          AI 구조화하기
        </button>
      </div>

      {message && (
        <p style={{ marginTop: "20px" }}>
          {message}
        </p>
      )}

      {/* 3. AI 구조화 결과 */}
      {structure && (
        <div style={{ marginTop: "30px" }}>
          <h2>3. AI 구조화 결과</h2>

          <h3>상황</h3>
          <p>
            {structure.situation ||
              "입력된 내용이 없습니다."}
          </p>

          <h3>문제</h3>
          <p>
            {structure.problem ||
              "입력된 내용이 없습니다."}
          </p>

          <h3>행동</h3>
          <p>
            {structure.action ||
              "입력된 내용이 없습니다."}
          </p>

          <h3>결과</h3>
          <p>
            {structure.result ||
              "입력된 내용이 없습니다."}
          </p>

          <h3>의미</h3>
          <p>
            {structure.meaning ||
              "입력된 내용이 없습니다."}
          </p>
        </div>
      )}

      {/* 4. 추가 질문 */}
      {hasMissingStructure && (
        <div style={{ marginTop: "30px" }}>
          <hr />

          <h2>4. 추가 질문</h2>

          <p>
            부족한 내용을 조금 더 알려주시면
            글의 구조를 완성할 수 있습니다.
          </p>

          {!structure.situation && (
            <div style={{ marginBottom: "20px" }}>
              <p>
                <strong>
                  이 경험은 어떤 상황에서 일어났나요?
                </strong>
              </p>

              <textarea
                value={followUpAnswers.situation}
                onChange={(e) =>
                  setFollowUpAnswers({
                    ...followUpAnswers,
                    situation: e.target.value,
                  })
                }
                placeholder="예: 새로운 카페에서 처음 아르바이트를 시작했을 때입니다."
                rows="3"
                style={{
                  width: "100%",
                  padding: "10px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}

          {!structure.problem && (
            <div style={{ marginBottom: "20px" }}>
              <p>
                <strong>
                  당시 어떤 문제나 어려움이 있었나요?
                </strong>
              </p>

              <textarea
                value={followUpAnswers.problem}
                onChange={(e) =>
                  setFollowUpAnswers({
                    ...followUpAnswers,
                    problem: e.target.value,
                  })
                }
                placeholder="예: 주문 실수가 자주 발생했습니다."
                rows="3"
                style={{
                  width: "100%",
                  padding: "10px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}

          {!structure.action && (
            <div style={{ marginBottom: "20px" }}>
              <p>
                <strong>
                  그 문제를 해결하기 위해 어떤 행동을 했나요?
                </strong>
              </p>

              <textarea
                value={followUpAnswers.action}
                onChange={(e) =>
                  setFollowUpAnswers({
                    ...followUpAnswers,
                    action: e.target.value,
                  })
                }
                placeholder="예: 메뉴를 외우고 반복해서 연습했습니다."
                rows="3"
                style={{
                  width: "100%",
                  padding: "10px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}

          {!structure.result && (
            <div style={{ marginBottom: "20px" }}>
              <p>
                <strong>
                  그 행동 이후 어떤 결과가 있었나요?
                </strong>
              </p>

              <textarea
                value={followUpAnswers.result}
                onChange={(e) =>
                  setFollowUpAnswers({
                    ...followUpAnswers,
                    result: e.target.value,
                  })
                }
                placeholder="예: 혼자서도 안정적으로 주문을 받을 수 있게 되었습니다."
                rows="3"
                style={{
                  width: "100%",
                  padding: "10px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}

          {!structure.meaning && (
            <div style={{ marginBottom: "20px" }}>
              <p>
                <strong>
                  이 경험을 통해 무엇을 배웠나요?
                </strong>
              </p>

              <textarea
                value={followUpAnswers.meaning}
                onChange={(e) =>
                  setFollowUpAnswers({
                    ...followUpAnswers,
                    meaning: e.target.value,
                  })
                }
                placeholder="예: 반복해서 익히고 확인하는 습관의 중요성을 배웠습니다."
                rows="3"
                style={{
                  width: "100%",
                  padding: "10px",
                  boxSizing: "border-box",
                }}
              />
            </div>
          )}

          <button
            onClick={submitFollowUp}
            style={{
              padding: "10px 20px",
              cursor: "pointer",
            }}
          >
            추가 내용 반영
          </button>
        </div>
      )}

      <hr />

      {/* 5. 초안 작성 */}
      <h2>5. 초안 작성</h2>

      <p>
        위 구조화 결과를 참고해서 직접 글을 작성해보세요.
      </p>

      <textarea
        value={draft}
        onChange={(e) =>
          setDraft(e.target.value)
        }
        placeholder="구조화된 내용을 참고해서 초안을 작성해주세요."
        rows="10"
        style={{
          width: "100%",
          padding: "12px",
          boxSizing: "border-box",
        }}
      />

      <div style={{ marginTop: "10px" }}>
        <button
          onClick={saveDraft}
          style={{
            padding: "10px 20px",
            cursor: "pointer",
          }}
        >
          초안 저장
        </button>

        <button
          onClick={loadDrafts}
          style={{
            marginLeft: "10px",
            padding: "10px 20px",
            cursor: "pointer",
          }}
        >
          저장된 초안 보기
        </button>
      </div>

      {/* 6. 저장된 초안 */}
      {drafts.length > 0 && (
        <div style={{ marginTop: "30px" }}>
          <hr />

          <h2>6. 저장된 초안</h2>

          {drafts.map((item) => (
            <div
              key={item.id}
              style={{
                border: "1px solid #ccc",
                padding: "15px",
                marginBottom: "15px",
              }}
            >
              <h3>
                버전 {item.version}
              </h3>

              <p
                style={{
                  whiteSpace: "pre-wrap",
                }}
              >
                {item.content}
              </p>

              <p>
                저장 시간: {item.created_at}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* 7. 초안 버전 비교 */}
      {drafts.length >= 2 && (
        <div style={{ marginTop: "40px" }}>
          <hr />

          <h2>7. 초안 버전 비교</h2>

          <p>
            비교할 두 버전을 선택해주세요.
          </p>

          <div
            style={{
              display: "flex",
              gap: "20px",
              marginBottom: "20px",
            }}
          >
            <div>
              <label>
                이전 버전

                <select
                  value={leftDraftId}
                  onChange={(e) =>
                    setLeftDraftId(e.target.value)
                  }
                  style={{
                    marginLeft: "10px",
                    padding: "8px",
                  }}
                >
                  <option value="">
                    버전 선택
                  </option>

                  {drafts.map((item) => (
                    <option
                      key={item.id}
                      value={item.id}
                    >
                      버전 {item.version}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div>
              <label>
                수정 버전

                <select
                  value={rightDraftId}
                  onChange={(e) =>
                    setRightDraftId(e.target.value)
                  }
                  style={{
                    marginLeft: "10px",
                    padding: "8px",
                  }}
                >
                  <option value="">
                    버전 선택
                  </option>

                  {drafts.map((item) => (
                    <option
                      key={item.id}
                      value={item.id}
                    >
                      버전 {item.version}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {leftDraft && rightDraft && (
            <div
              style={{
                display: "flex",
                gap: "20px",
              }}
            >
              <div
                style={{
                  flex: 1,
                  border: "1px solid #ccc",
                  padding: "15px",
                }}
              >
                <h3>
                  버전 {leftDraft.version}
                </h3>

                <p
                  style={{
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {leftDraft.content}
                </p>
              </div>

              <div
                style={{
                  flex: 1,
                  border: "1px solid #ccc",
                  padding: "15px",
                }}
              >
                <h3>
                  버전 {rightDraft.version}
                </h3>

                <p
                  style={{
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {rightDraft.content}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Writing;