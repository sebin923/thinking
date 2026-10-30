// =============================================================
// AdminPage.jsx — 관리자 페이지
// -------------------------------------------------------------
// 기획서 구조 그대로 탭 3개
//   1. 퀴즈 관리: 문제·정답·해설 추가 / 수정 / 삭제
//   2. 회원 관리: 회원 조회(검색·상태 필터) + 이용 상태 관리(정상 ↔ 정지)
//   3. 랭킹 관리: 도전 점수·기록 조회 / 삭제
//
// 들어올 수 있는 사람: 로그인한 관리자(role = "admin")만
//   - 화면에서도 막고(헤더에 버튼이 안 보이고, 들어와도 안내만 보임)
//   - 서버에서도 막음(routers/admin.py가 관리자가 아니면 403) ← 진짜 보안은 서버 쪽
//
// 데이터: 백엔드 routers/admin.py (주소는 /api/admin/...)
// =============================================================

import { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  ListChecks,
  Users,
  Trophy,
  Plus,
  Pencil,
  Trash2,
  X,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Loader2,
  LogIn,
  Lock,
  CheckCircle2,
} from "lucide-react";

import PageHero from "../components/PageHero";
import ConfirmModal from "../components/ConfirmModal";
import {
  fetchAdminQuizzes,
  createQuiz,
  updateQuiz,
  deleteQuiz,
  fetchAdminUsers,
  changeUserStatus,
  fetchAdminRankings,
  deleteRanking,
} from "../api/admin";
import { QUIZ_CATEGORIES } from "../data/quizCategories";
import { formatPhone } from "../utils/validation";
// 로딩 아이콘이 빙글빙글 도는 .spin 클래스가 들어 있는 파일
import "../components/AuthLayout.css";
import "./AdminPage.css";

// ----- 탭 목록 (기획서 그림의 세 칸) -----
const TABS = [
  { key: "quiz", label: "퀴즈 관리", icon: ListChecks },
  { key: "users", label: "회원 관리", icon: Users },
  { key: "rankings", label: "랭킹 관리", icon: Trophy },
];

// 보기 개수 제한 (서버 admin_schemas.py의 QuizIn과 똑같이 맞춤)
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 6;

// 목록 한 페이지에 보여줄 개수 (퀴즈·회원·랭킹 공통) — 바꾸고 싶으면 이 숫자만 고치면 됨
const PAGE_SIZE = 10;

// ----- 목록을 페이지로 나누기 (페이지네이션) -----
// list: 전체 목록, page: 보고 싶은 페이지 번호(1부터)
// 돌려주는 값: { items: 그 페이지에 보여줄 것들, currentPage: 실제 페이지, totalPages: 전체 페이지 수 }
function paginate(list, page) {
  // 23개면 23 / 10 = 2.3 → 올림(Math.ceil)해서 3페이지 (최소 1페이지)
  const totalPages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  // 삭제 등으로 페이지 수가 줄었는데 지금 페이지가 더 크면 마지막 페이지로
  const currentPage = Math.min(page, totalPages);
  // slice(시작, 끝): 1페이지는 0~9번, 2페이지는 10~19번
  const items = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  return { items, currentPage, totalPages };
}

// ----- 날짜 → "2026.10.27" -----
function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const month = String(date.getMonth() + 1).padStart(2, "0"); // getMonth()는 0부터 시작해서 +1
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}.${month}.${day}`;
}

// ----- 서버 에러 공통 처리 -----
// 401(로그인 풀림)이면 App에 알려서 로그인 화면으로 보내고 true를 돌려줌 → 부르는 쪽은 그냥 멈추면 됨
function handleAuthError(err, onSessionExpired) {
  if (err.status === 401) {
    onSessionExpired?.(); // ?.(): 함수가 있을 때만 실행
    return true;
  }
  return false;
}

// props
//  - auth: 로그인 정보 { token, user } (로그인 안 했으면 null)
//  - onGoLogin: 로그인 안 했을 때 "로그인하기" 버튼
//  - onSessionExpired: 토큰이 만료됐을 때 (App이 로그아웃시키고 로그인 화면으로 보냄)
function AdminPage({ auth, onGoLogin, onSessionExpired }) {
  // tab: 지금 보고 있는 탭 (처음엔 퀴즈 관리)
  const [tab, setTab] = useState("quiz");

  const hero = (
    <PageHero
      eyebrow="관리자 전용"
      title="관리자 페이지"
      description={"퀴즈 문제, 회원 이용 상태, 랭킹 기록을 관리해요.\n변경 내용은 사용자 화면에 바로 반영돼요."}
      memoText={"꼼꼼하게\n관리하기\n:)"}
      memoVariant="notebook"
    />
  );

  // ----- 로그인 안 했거나 관리자가 아닐 때 -----
  // (헤더에 관리자 버튼이 안 보이니 보통은 못 들어오지만, 혹시 들어와도 안내만 보여줌)
  if (!auth?.token || auth.user?.role !== "admin") {
    return (
      <div className="sub-page">
        <div className="sub-page-inner">
          {hero}
          <section className="panel admin-message">
            {auth?.token ? <Lock size={36} strokeWidth={1.6} /> : <LogIn size={36} strokeWidth={1.6} />}
            <p>{auth?.token ? "관리자만 이용할 수 있는 페이지예요." : "관리자 계정으로 로그인해 주세요."}</p>
            {!auth?.token && (
              <button type="button" className="btn-primary" onClick={onGoLogin}>
                로그인하기
              </button>
            )}
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="sub-page">
      <div className="sub-page-inner">
        {hero}

        {/* ----- 탭 버튼 ----- */}
        {/* role="tablist" / "tab": 화면 읽기 프로그램에 "탭 묶음"이라고 알려줌 */}
        <div className="admin-tabs" role="tablist" aria-label="관리 메뉴">
          {TABS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                type="button"
                role="tab"
                aria-selected={tab === item.key}
                className={tab === item.key ? "admin-tab active" : "admin-tab"}
                onClick={() => setTab(item.key)}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </div>

        {/*
          ----- 탭 내용 -----
          고른 탭 하나만 그림 → 탭을 바꾸면 그 탭 화면이 새로 만들어지면서 최신 데이터를 다시 불러옴
        */}
        <section className="panel admin-panel" role="tabpanel">
          {tab === "quiz" && <QuizManager token={auth.token} onSessionExpired={onSessionExpired} />}
          {tab === "users" && (
            <UserManager token={auth.token} myUserId={auth.user.user_id} onSessionExpired={onSessionExpired} />
          )}
          {tab === "rankings" && <RankingManager token={auth.token} onSessionExpired={onSessionExpired} />}
        </section>
      </div>
    </div>
  );
}

// =============================================================
// 1. 퀴즈 관리
// =============================================================

// 빈 입력 폼 (새 문제 추가할 때 시작 값)
// answerIndex: 몇 번째 보기가 정답인지 (0부터 셈, -1이면 아직 안 고름)
const emptyQuizForm = (category) => ({
  category,
  question: "",
  options: ["", ""],
  answerIndex: -1,
  explanation: "",
});

function QuizManager({ token, onSessionExpired }) {
  const [category, setCategory] = useState("spelling"); // 지금 보고 있는 종류
  const [quizzes, setQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0); // +1 하면 목록을 다시 불러옴
  const [keyword, setKeyword] = useState(""); // 문제 검색어 (화면에서만 거름)
  const [page, setPage] = useState(1); // 지금 보고 있는 페이지 (10개씩)

  // editor: 입력 폼 상태 (null이면 폼 닫힘)
  //  { quizId: 수정할 퀴즈 번호(새 문제면 null), form: 입력값, saving: 저장 중인지, error: 실패 문구 }
  const [editor, setEditor] = useState(null);
  // confirm: 삭제 확인창 { quiz, busy, error } (null이면 안 보임)
  const [confirm, setConfirm] = useState(null);
  // notice: 잠깐 보여줄 성공 문구
  const [notice, setNotice] = useState("");

  // ----- 목록 불러오기 (종류가 바뀌거나 reloadKey가 바뀔 때) -----
  useEffect(() => {
    let ignore = false; // 응답이 오기 전에 종류를 또 바꾸면 이전 응답은 무시
    fetchAdminQuizzes(token, category)
      .then((data) => {
        if (ignore) return;
        setQuizzes(data);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore || handleAuthError(err, onSessionExpired)) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [token, category, reloadKey, onSessionExpired]);

  // 종류 바꾸기 (맞춤법 ↔ 문법)
  const handleCategory = (key) => {
    if (key === category) return;
    setLoading(true);
    setCategory(key);
    setPage(1); // 종류가 바뀌면 1페이지부터
  };

  // 성공 문구를 3초 동안 보여주기
  const showNotice = (message) => {
    setNotice(message);
    setTimeout(() => setNotice(""), 3000);
  };

  // ----- 입력 폼 열기 -----
  const openNew = () => setEditor({ quizId: null, form: emptyQuizForm(category), saving: false, error: "" });
  const openEdit = (quiz) =>
    setEditor({
      quizId: quiz.quiz_id,
      form: {
        category: quiz.category,
        question: quiz.question,
        // map(String): 보기가 숫자 등으로 들어 있어도 입력칸에 넣을 수 있게 글자로 바꿈
        options: quiz.options.map(String),
        // indexOf: 정답이 몇 번째 보기인지 (없으면 -1)
        answerIndex: quiz.options.map(String).indexOf(quiz.answer),
        explanation: quiz.explanation || "",
      },
      saving: false,
      error: "",
    });

  // 폼 안의 값 하나 바꾸기 (예: updateForm({ question: "..." }))
  // prev => ({ ...prev, ... }): 나머지 값은 그대로 두고 바뀐 칸만 덮어씀
  const updateForm = (changes) =>
    setEditor((prev) => ({ ...prev, error: "", form: { ...prev.form, ...changes } }));

  // 보기 하나 고치기
  const changeOption = (index, value) => {
    const options = editor.form.options.map((option, i) => (i === index ? value : option));
    updateForm({ options });
  };

  // 보기 칸 추가 (최대 6개)
  const addOption = () => {
    if (editor.form.options.length >= MAX_OPTIONS) return;
    updateForm({ options: [...editor.form.options, ""] });
  };

  // 보기 칸 빼기 (최소 2개) → 정답으로 골라 둔 보기가 지워지거나 앞으로 당겨지면 번호도 맞춰 줌
  const removeOption = (index) => {
    const { options, answerIndex } = editor.form;
    if (options.length <= MIN_OPTIONS) return;
    let nextAnswer = answerIndex;
    if (index === answerIndex) nextAnswer = -1; // 정답 보기를 지움 → 다시 골라야 함
    else if (index < answerIndex) nextAnswer = answerIndex - 1; // 앞쪽 보기를 지움 → 한 칸씩 당겨짐
    updateForm({ options: options.filter((_, i) => i !== index), answerIndex: nextAnswer });
  };

  // ----- 저장 (추가 또는 수정) -----
  const handleSave = async (event) => {
    event.preventDefault(); // form 제출 시 페이지가 새로고침되는 기본 동작 막기
    const { form, quizId } = editor;

    // 화면에서 먼저 간단히 검사 (서버도 똑같이 검사함)
    const filled = form.options.map((option) => option.trim());
    if (!form.question.trim()) return setEditor((prev) => ({ ...prev, error: "문제를 입력해 주세요." }));
    if (filled.filter(Boolean).length < MIN_OPTIONS)
      return setEditor((prev) => ({ ...prev, error: "보기는 2개 이상 입력해 주세요." }));
    if (form.answerIndex < 0 || !filled[form.answerIndex])
      return setEditor((prev) => ({ ...prev, error: "정답 보기를 골라 주세요. (보기 왼쪽 동그라미)" }));

    const payload = {
      category: form.category,
      question: form.question,
      options: filled.filter(Boolean), // 빈 보기 칸은 빼고 보냄
      answer: filled[form.answerIndex],
      explanation: form.explanation,
    };

    setEditor((prev) => ({ ...prev, saving: true, error: "" }));
    try {
      if (quizId) await updateQuiz(token, quizId, payload);
      else await createQuiz(token, payload);
    } catch (err) {
      if (handleAuthError(err, onSessionExpired)) return;
      setEditor((prev) => ({ ...prev, saving: false, error: err.message }));
      return;
    }

    setEditor(null);
    showNotice(quizId ? "퀴즈를 수정했어요." : "퀴즈를 추가했어요.");
    // 저장한 문제의 종류 목록을 보여줌 (다른 종류로 저장했으면 그쪽으로 이동)
    setLoading(true);
    setPage(1); // 새 문제·수정한 문제는 목록 맨 위 쪽이라 1페이지로
    if (form.category !== category) setCategory(form.category);
    else setReloadKey((key) => key + 1);
  };

  // ----- 삭제 -----
  // useCallback: 확인창의 Esc 키 처리(useEffect)가 쓸데없이 다시 등록되지 않게 함수를 고정
  const closeConfirm = useCallback(() => setConfirm(null), []);
  const handleDelete = async () => {
    const { quiz } = confirm;
    setConfirm((prev) => ({ ...prev, busy: true, error: "" }));
    try {
      await deleteQuiz(token, quiz.quiz_id);
    } catch (err) {
      if (handleAuthError(err, onSessionExpired)) return;
      setConfirm((prev) => ({ ...prev, busy: false, error: err.message }));
      return;
    }
    // 서버에 다시 묻지 않고 화면 목록에서 바로 빼기
    setQuizzes((prev) => prev.filter((item) => item.quiz_id !== quiz.quiz_id));
    setConfirm(null);
    showNotice("퀴즈를 삭제했어요.");
  };

  // 검색어로 거른 목록 (문제·보기·해설 중 하나에 들어 있으면 보여줌)
  const text = keyword.trim();
  const visible = text
    ? quizzes.filter((quiz) =>
        [quiz.question, quiz.explanation || "", ...quiz.options.map(String)].some((value) => value.includes(text))
      )
    : quizzes;
  // 지금 페이지에 보여줄 10개
  const quizPage = paginate(visible, page);

  return (
    <>
      {/* ----- 위쪽 도구 줄: 종류 버튼 + 검색 + 추가 ----- */}
      <div className="admin-toolbar">
        <div className="admin-chips" role="group" aria-label="퀴즈 종류">
          {QUIZ_CATEGORIES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={category === item.key ? "admin-chip active" : "admin-chip"}
              aria-pressed={category === item.key}
              onClick={() => handleCategory(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <label className="admin-search">
          <Search size={16} />
          <input
            type="search"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1); // 검색어가 바뀌면 1페이지부터
            }}
            placeholder="문제·보기·해설 검색"
            aria-label="퀴즈 검색"
          />
        </label>

        <button type="button" className="admin-primary" onClick={openNew} disabled={editor !== null}>
          <Plus size={16} /> 문제 추가
        </button>
      </div>

      {notice && (
        <p className="admin-notice" role="status">
          <CheckCircle2 size={16} /> {notice}
        </p>
      )}

      {/* ----- 입력 폼 (추가·수정할 때만 보임) ----- */}
      {editor && (
        <form className="admin-form" onSubmit={handleSave}>
          <div className="admin-form-head">
            <strong>{editor.quizId ? "퀴즈 수정" : "새 퀴즈 추가"}</strong>
            <button type="button" className="admin-icon-button" onClick={() => setEditor(null)} aria-label="닫기">
              <X size={18} />
            </button>
          </div>

          {/* 종류 */}
          <div className="admin-field">
            <span className="admin-label">종류</span>
            <div className="admin-chips">
              {QUIZ_CATEGORIES.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={editor.form.category === item.key ? "admin-chip active" : "admin-chip"}
                  aria-pressed={editor.form.category === item.key}
                  onClick={() => updateForm({ category: item.key })}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* 문제 */}
          <label className="admin-field">
            <span className="admin-label">문제</span>
            <textarea
              value={editor.form.question}
              onChange={(event) => updateForm({ question: event.target.value })}
              placeholder="예: 친구와 약속을 했으면 '____' 지켜야 한다."
              rows={2}
              maxLength={500}
            />
            <small className="admin-hint">빈칸은 ____ (밑줄 4개)로 표시하면 퀴즈 화면과 똑같이 보여요.</small>
          </label>

          {/* 보기 + 정답 고르기 */}
          <div className="admin-field">
            <span className="admin-label">보기 (왼쪽 동그라미로 정답 선택)</span>
            <ul className="admin-options">
              {editor.form.options.map((option, index) => (
                // key에 index를 쓰는 이유: 보기는 순서 자체가 의미라서 칸 위치로 구분해도 됨
                <li key={index} className={editor.form.answerIndex === index ? "is-answer" : ""}>
                  <input
                    type="radio"
                    name="quiz-answer"
                    checked={editor.form.answerIndex === index}
                    onChange={() => updateForm({ answerIndex: index })}
                    aria-label={`${index + 1}번 보기를 정답으로`}
                  />
                  <input
                    type="text"
                    value={option}
                    onChange={(event) => changeOption(index, event.target.value)}
                    placeholder={`보기 ${index + 1}`}
                    maxLength={100}
                  />
                  {editor.form.answerIndex === index && <span className="admin-answer-tag">정답</span>}
                  <button
                    type="button"
                    className="admin-icon-button"
                    onClick={() => removeOption(index)}
                    disabled={editor.form.options.length <= MIN_OPTIONS}
                    aria-label={`${index + 1}번 보기 지우기`}
                  >
                    <X size={16} />
                  </button>
                </li>
              ))}
            </ul>
            {editor.form.options.length < MAX_OPTIONS && (
              <button type="button" className="admin-text-button" onClick={addOption}>
                <Plus size={14} /> 보기 추가
              </button>
            )}
          </div>

          {/* 해설 */}
          <label className="admin-field">
            <span className="admin-label">해설 (선택)</span>
            <textarea
              value={editor.form.explanation}
              onChange={(event) => updateForm({ explanation: event.target.value })}
              placeholder="정답인 이유를 적어 주세요. 문제를 푼 뒤 사용자에게 보여요."
              rows={3}
              maxLength={1000}
            />
          </label>

          {editor.error && (
            <p className="admin-error" role="alert">
              {editor.error}
            </p>
          )}

          <div className="admin-form-actions">
            <button type="button" className="admin-secondary" onClick={() => setEditor(null)} disabled={editor.saving}>
              취소
            </button>
            <button type="submit" className="admin-primary" disabled={editor.saving}>
              {editor.saving ? (
                <>
                  <Loader2 size={16} className="spin" /> 저장하는 중...
                </>
              ) : editor.quizId ? (
                "수정 저장"
              ) : (
                "추가하기"
              )}
            </button>
          </div>
        </form>
      )}

      {/* ----- 목록 ----- */}
      <ListState
        loading={loading}
        error={error}
        empty={visible.length === 0}
        emptyText={text ? "검색 결과가 없어요." : "등록된 문제가 없어요. '문제 추가'로 첫 문제를 만들어 보세요."}
        onRetry={() => {
          setLoading(true);
          setReloadKey((key) => key + 1);
        }}
      >
        <p className="admin-count">총 {visible.length}문제</p>
        <ul className="admin-list">
          {quizPage.items.map((quiz) => (
            <li key={quiz.quiz_id} className="admin-item">
              <div className="admin-item-main">
                <p className="admin-quiz-question">{quiz.question}</p>
                {/* 보기 목록 (정답은 초록색) */}
                <div className="admin-quiz-options">
                  {quiz.options.map((option) => (
                    <span
                      key={String(option)}
                      className={String(option) === quiz.answer ? "admin-option correct" : "admin-option"}
                    >
                      {String(option) === quiz.answer && <CheckCircle2 size={13} />}
                      {String(option)}
                    </span>
                  ))}
                </div>
                {quiz.explanation && <p className="admin-quiz-explanation">{quiz.explanation}</p>}
                <p className="admin-meta">
                  #{quiz.quiz_id} · {formatDate(quiz.created_at)} 등록 · 푼 횟수 {quiz.solved_count}회
                </p>
              </div>
              <div className="admin-item-actions">
                <button
                  type="button"
                  className="admin-secondary small"
                  onClick={() => openEdit(quiz)}
                  disabled={editor !== null}
                >
                  <Pencil size={14} /> 수정
                </button>
                <button
                  type="button"
                  className="admin-danger small"
                  onClick={() => setConfirm({ quiz, busy: false, error: "" })}
                >
                  <Trash2 size={14} /> 삭제
                </button>
              </div>
            </li>
          ))}
        </ul>
        <Pagination page={quizPage.currentPage} totalPages={quizPage.totalPages} onChange={setPage} label="퀴즈 목록 페이지" />
      </ListState>

      {confirm && (
        <ConfirmModal
          danger
          title="이 퀴즈를 삭제할까요?"
          message={`"${confirm.quiz.question}"\n사용자들이 이 문제를 푼 기록(${confirm.quiz.solved_count}회)도 함께 지워지고,\n되돌릴 수 없어요.`}
          confirmLabel="삭제하기"
          busy={confirm.busy}
          error={confirm.error}
          onCancel={closeConfirm}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

// =============================================================
// 2. 회원 관리
// =============================================================

// 상태 필터 버튼 ("" = 전체)
const STATUS_FILTERS = [
  { key: "", label: "전체" },
  { key: "active", label: "정상" },
  { key: "suspended", label: "정지" },
];

function UserManager({ token, myUserId, onSessionExpired }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [input, setInput] = useState(""); // 검색창에 지금 쓰고 있는 글자
  // filters: 실제로 서버에 보낸 조건 (검색 버튼·엔터를 눌러야 바뀜 → 글자 칠 때마다 서버에 안 물어봄)
  const [filters, setFilters] = useState({ q: "", status: "" });
  const [reloadKey, setReloadKey] = useState(0);
  const [confirm, setConfirm] = useState(null); // 상태 변경 확인창 { user, next, busy, error }
  const [page, setPage] = useState(1); // 지금 보고 있는 페이지 (10명씩)

  useEffect(() => {
    let ignore = false;
    fetchAdminUsers(token, filters)
      .then((data) => {
        if (ignore) return;
        setUsers(data);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore || handleAuthError(err, onSessionExpired)) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [token, filters, reloadKey, onSessionExpired]);

  // 검색 (엔터 또는 검색 버튼)
  const handleSearch = (event) => {
    event.preventDefault();
    setLoading(true);
    setPage(1); // 검색하면 1페이지부터
    setFilters((prev) => ({ ...prev, q: input.trim() }));
  };

  // 상태 필터 (전체 / 정상 / 정지)
  const handleStatusFilter = (key) => {
    if (key === filters.status) return;
    setLoading(true);
    setPage(1); // 필터를 바꾸면 1페이지부터
    setFilters((prev) => ({ ...prev, status: key }));
  };

  const closeConfirm = useCallback(() => setConfirm(null), []);

  // ----- 이용 상태 바꾸기 (확인창의 확인 버튼) -----
  const handleChangeStatus = async () => {
    const { user, next } = confirm;
    setConfirm((prev) => ({ ...prev, busy: true, error: "" }));
    let updated;
    try {
      updated = await changeUserStatus(token, user.user_id, next);
    } catch (err) {
      if (handleAuthError(err, onSessionExpired)) return;
      setConfirm((prev) => ({ ...prev, busy: false, error: err.message }));
      return;
    }
    // 목록에서 그 회원 한 줄만 서버가 돌려준 새 값으로 바꿔 끼움
    // (상태 필터가 걸려 있으면 더 이상 조건에 안 맞는 회원은 목록에서 뺌)
    setUsers((prev) =>
      prev
        .map((item) => (item.user_id === updated.user_id ? updated : item))
        .filter((item) => !filters.status || item.status === filters.status)
    );
    setConfirm(null);
  };

  const suspendedCount = users.filter((user) => user.status === "suspended").length;
  // 지금 페이지에 보여줄 10명
  const userPage = paginate(users, page);

  return (
    <>
      <div className="admin-toolbar">
        <div className="admin-chips" role="group" aria-label="이용 상태로 거르기">
          {STATUS_FILTERS.map((item) => (
            <button
              key={item.key || "all"}
              type="button"
              className={filters.status === item.key ? "admin-chip active" : "admin-chip"}
              aria-pressed={filters.status === item.key}
              onClick={() => handleStatusFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* form으로 감싸면 엔터를 눌러도 검색됨 */}
        <form className="admin-search" onSubmit={handleSearch} role="search">
          <Search size={16} />
          <input
            type="search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="아이디·이름·이메일 검색"
            aria-label="회원 검색"
          />
          <button type="submit" className="admin-text-button">
            검색
          </button>
        </form>
      </div>

      <ListState
        loading={loading}
        error={error}
        empty={users.length === 0}
        emptyText={filters.q || filters.status ? "조건에 맞는 회원이 없어요." : "아직 가입한 회원이 없어요."}
        onRetry={() => {
          setLoading(true);
          setReloadKey((key) => key + 1);
        }}
      >
        <p className="admin-count">
          총 {users.length}명{suspendedCount > 0 && ` · 정지 ${suspendedCount}명`}
        </p>
        <ul className="admin-list">
          {userPage.items.map((user) => {
            const isSuspended = user.status === "suspended";
            const isAdmin = user.role === "admin";
            const isMe = user.user_id === myUserId;
            return (
              <li key={user.user_id} className={isSuspended ? "admin-item suspended" : "admin-item"}>
                <div className="admin-item-main">
                  <p className="admin-user-name">
                    <strong>{user.name}</strong>
                    <span className="admin-user-id">@{user.login_id}</span>
                    {isAdmin && <span className="admin-badge admin">관리자</span>}
                    <span className={isSuspended ? "admin-badge suspended" : "admin-badge active"}>
                      {isSuspended ? "이용 정지" : "정상"}
                    </span>
                    {isMe && <span className="admin-badge me">나</span>}
                  </p>
                  <p className="admin-user-contact">
                    {user.email} · {formatPhone(user.phone)}
                  </p>
                  <p className="admin-meta">
                    {formatDate(user.created_at)} 가입 · 쓴 글 {user.document_count}편 · 도전 {user.ranking_count}회
                    {user.ranking_count > 0 && ` (최고 ${user.best_score}점)`}
                  </p>
                </div>
                <div className="admin-item-actions">
                  {/* 관리자 계정·내 계정은 정지 버튼을 안 보여줌 (서버도 막아 둠) */}
                  {isAdmin || isMe ? (
                    <span className="admin-muted">변경 불가</span>
                  ) : isSuspended ? (
                    <button
                      type="button"
                      className="admin-secondary small"
                      onClick={() => setConfirm({ user, next: "active", busy: false, error: "" })}
                    >
                      정지 해제
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="admin-danger small"
                      onClick={() => setConfirm({ user, next: "suspended", busy: false, error: "" })}
                    >
                      이용 정지
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        <Pagination page={userPage.currentPage} totalPages={userPage.totalPages} onChange={setPage} label="회원 목록 페이지" />
      </ListState>

      {confirm && (
        <ConfirmModal
          title={confirm.next === "suspended" ? "이 회원을 이용 정지할까요?" : "이용 정지를 해제할까요?"}
          message={
            confirm.next === "suspended"
              ? `${confirm.user.name} (@${confirm.user.login_id})\n정지하면 이 회원은 로그인할 수 없고,\n로그인해 있어도 바로 이용이 막혀요.`
              : `${confirm.user.name} (@${confirm.user.login_id})\n해제하면 다시 로그인해서 이용할 수 있어요.`
          }
          confirmLabel={confirm.next === "suspended" ? "정지하기" : "해제하기"}
          busy={confirm.busy}
          error={confirm.error}
          onCancel={closeConfirm}
          onConfirm={handleChangeStatus}
        />
      )}
    </>
  );
}

// =============================================================
// 3. 랭킹 관리
// =============================================================

function RankingManager({ token, onSessionExpired }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [keyword, setKeyword] = useState(""); // 이름·아이디 검색 (화면에서만 거름)
  const [confirm, setConfirm] = useState(null); // 삭제 확인창 { row, busy, error }
  const [page, setPage] = useState(1); // 지금 보고 있는 페이지 (10개씩)

  useEffect(() => {
    let ignore = false;
    fetchAdminRankings(token, "spelling") // 랭킹은 맞춤법 도전 모드만 있음
      .then((data) => {
        if (ignore) return;
        setRows(data);
        setError("");
        setLoading(false);
      })
      .catch((err) => {
        if (ignore || handleAuthError(err, onSessionExpired)) return;
        setError(err.message);
        setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [token, reloadKey, onSessionExpired]);

  const closeConfirm = useCallback(() => setConfirm(null), []);

  const handleDelete = async () => {
    const { row } = confirm;
    setConfirm((prev) => ({ ...prev, busy: true, error: "" }));
    try {
      await deleteRanking(token, row.ranking_id);
    } catch (err) {
      if (handleAuthError(err, onSessionExpired)) return;
      setConfirm((prev) => ({ ...prev, busy: false, error: err.message }));
      return;
    }
    setRows((prev) => prev.filter((item) => item.ranking_id !== row.ranking_id));
    setConfirm(null);
  };

  // 순위는 검색과 상관없이 "전체 기록에서 몇 번째인지"로 매김 (검색해도 번호가 안 바뀌게)
  const ranked = rows.map((row, index) => ({ ...row, order: index + 1 }));
  const text = keyword.trim();
  const visible = text
    ? ranked.filter((row) => (row.name || "").includes(text) || (row.login_id || "").includes(text))
    : ranked;
  // 지금 페이지에 보여줄 10개 (순번은 위에서 매긴 전체 순번 그대로)
  const rankingPage = paginate(visible, page);
  // 서로 다른 도전자 수 (Set: 중복 없는 묶음)
  const playerCount = new Set(rows.map((row) => row.user_id)).size;

  return (
    <>
      <div className="admin-toolbar">
        <p className="admin-hint wide">
          모든 도전 기록이에요. 랭킹 화면에는 사람마다 최고 기록 1개만 보여요.
          <br />
          비정상적인 기록을 지우면 랭킹 화면에서도 바로 빠져요.
        </p>
        <label className="admin-search">
          <Search size={16} />
          <input
            type="search"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1); // 검색어가 바뀌면 1페이지부터
            }}
            placeholder="이름·아이디 검색"
            aria-label="랭킹 기록 검색"
          />
        </label>
      </div>

      <ListState
        loading={loading}
        error={error}
        empty={visible.length === 0}
        emptyText={text ? "검색 결과가 없어요." : "아직 도전 기록이 없어요."}
        onRetry={() => {
          setLoading(true);
          setReloadKey((key) => key + 1);
        }}
      >
        <p className="admin-count">
          기록 {rows.length}개 · 도전자 {playerCount}명
        </p>
        {/* 표(table): 순위·이름·점수·시간·날짜처럼 같은 칸을 비교해서 보는 데이터라 표가 알맞음 */}
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th scope="col">순번</th>
                <th scope="col">도전자</th>
                <th scope="col">점수</th>
                <th scope="col">걸린 시간</th>
                <th scope="col">도전일</th>
                <th scope="col">
                  <span className="sr-only">관리</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rankingPage.items.map((row) => (
                <tr key={row.ranking_id}>
                  <td className="num">{row.order}</td>
                  <td>
                    {row.name ? (
                      <>
                        <strong>{row.name}</strong> <span className="admin-user-id">@{row.login_id}</span>
                      </>
                    ) : (
                      <span className="admin-muted">탈퇴한 회원</span>
                    )}
                  </td>
                  <td className="num strong">{row.score}문제</td>
                  <td className="num">{Number(row.elapsed_time || 0).toFixed(1)}초</td>
                  <td className="num">{formatDate(row.challenged_at)}</td>
                  <td className="right">
                    <button
                      type="button"
                      className="admin-danger small"
                      onClick={() => setConfirm({ row, busy: false, error: "" })}
                      aria-label={`${row.name || "탈퇴한 회원"} ${row.score}문제 기록 삭제`}
                    >
                      <Trash2 size={14} /> 삭제
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
          page={rankingPage.currentPage}
          totalPages={rankingPage.totalPages}
          onChange={setPage}
          label="랭킹 기록 페이지"
        />
      </ListState>

      {confirm && (
        <ConfirmModal
          danger
          title="이 도전 기록을 삭제할까요?"
          message={`${confirm.row.name || "탈퇴한 회원"} · ${confirm.row.score}문제 · ${Number(
            confirm.row.elapsed_time || 0
          ).toFixed(1)}초\n삭제하면 랭킹에서 빠지고, 되돌릴 수 없어요.`}
          confirmLabel="삭제하기"
          busy={confirm.busy}
          error={confirm.error}
          onCancel={closeConfirm}
          onConfirm={handleDelete}
        />
      )}
    </>
  );
}

// =============================================================
// 공통: 페이지 번호 (페이지네이션)
// =============================================================
// page: 지금 페이지, totalPages: 전체 페이지 수, onChange: 번호를 누르면 그 번호로 실행, label: 화면 읽기용 이름
// 1페이지뿐이어도 항상 보여줌 (‹ 1 › — 화살표는 둘 다 흐리게 막힘)
function Pagination({ page, totalPages, onChange, label }) {

  // 보여줄 번호: 페이지가 많으면 지금 페이지 근처 최대 5개만 (예: 3 4 [5] 6 7)
  const start = Math.max(1, Math.min(page - 2, totalPages - 4));
  const end = Math.min(totalPages, start + 4);
  // Array.from({ length: n }, (_, i) => ...): n개짜리 배열을 만들면서 값 채우기
  const numbers = Array.from({ length: end - start + 1 }, (_, i) => start + i);

  // 페이지 이동: 번호를 바꾸고 탭 위치로 부드럽게 스크롤 (목록 맨 위부터 보이게)
  const go = (next) => {
    if (next < 1 || next > totalPages || next === page) return;
    onChange(next);
    document.querySelector(".admin-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    // nav: "이동 메뉴" 태그 → 화면 읽기 프로그램이 페이지 이동 버튼 묶음으로 알아들음
    <nav className="admin-pagination" aria-label={label}>
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page - 1)}
        disabled={page === 1}
        aria-label="이전 페이지"
      >
        <ChevronLeft size={18} />
      </button>
      {numbers.map((number) => (
        <button
          key={number}
          type="button"
          className={number === page ? "admin-page active" : "admin-page"}
          onClick={() => go(number)}
          aria-current={number === page ? "page" : undefined} // 지금 보고 있는 페이지 표시
        >
          {number}
        </button>
      ))}
      <button
        type="button"
        className="admin-page-arrow"
        onClick={() => go(page + 1)}
        disabled={page === totalPages}
        aria-label="다음 페이지"
      >
        <ChevronRight size={18} />
      </button>
    </nav>
  );
}

// =============================================================
// 공통: 불러오는 중 / 실패 / 비어 있음 / 목록 보여주기
// =============================================================
// children: 정상일 때 보여줄 목록 (부모가 태그 사이에 넣은 내용)
function ListState({ loading, error, empty, emptyText, onRetry, children }) {
  if (loading) {
    return (
      <p className="admin-state">
        <Loader2 size={18} className="spin" /> 불러오는 중이에요...
      </p>
    );
  }
  if (error) {
    return (
      <div className="admin-state">
        <p>{error}</p>
        <button type="button" className="admin-secondary small" onClick={onRetry}>
          <RefreshCw size={14} /> 다시 불러오기
        </button>
      </div>
    );
  }
  if (empty) {
    return (
      <p className="admin-state">
        <ShieldCheck size={18} /> {emptyText}
      </p>
    );
  }
  return children;
}

export default AdminPage;
