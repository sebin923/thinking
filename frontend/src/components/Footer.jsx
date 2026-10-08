// =============================================================
// Footer.jsx — 페이지 맨 아래 정보 영역 (푸터)
// -------------------------------------------------------------
// 왼쪽: 로고 + 한 줄 소개
// 가운데·오른쪽: 메뉴 링크 묶음 (서비스 / 고객지원)
// 맨 아래: 팀 정보 + 저작권 표시
// 모든 페이지 아래에 똑같이 붙으니까 컴포넌트로 따로 분리함
// =============================================================

// 푸터 링크 묶음
// 묶음(제목 + 링크 여러 개)을 배열로 만들어두면, 아래에서 map 두 번으로 전부 그릴 수 있음
// key: 메뉴를 구분하는 이름 → Header의 메뉴 key와 똑같이 맞춰서 눌렀을 때 같은 화면으로 이동
const FOOTER_LINKS = [
  {
    title: "서비스",
    links: [
      { key: "home", label: "홈" },
      { key: "about", label: "서비스 소개" },
      { key: "write", label: "글쓰기 학습" },
      { key: "quiz", label: "퀴즈" },
      { key: "ranking", label: "랭킹" },
      { key: "guide", label: "이용안내" },
    ],
  },
  {
    title: "고객지원",
    links: [
      { key: "notice", label: "공지사항" },
      { key: "terms", label: "이용약관" },
      { key: "privacy", label: "개인정보처리방침" },
    ],
  },
];

// Footer 컴포넌트
// props: onNavClick → 링크를 눌렀을 때 실행할 함수 (App이 넘겨줌, Header와 같은 함수)
function Footer({ onNavClick }) {
  // 링크를 눌렀을 때: 해당 화면으로 바꾸고, 화면 맨 위로 스크롤
  const handleClick = (key) => {
    onNavClick(key);
    // window.scrollTo: 브라우저 스크롤 위치를 옮기는 함수
    // behavior: "smooth" → 순간이동 말고 부드럽게 올라가기
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    // <footer>: 페이지의 바닥 부분이라는 의미의 HTML 태그
    <footer className="footer">
      <div className="footer-inner">
        {/* ===== 위쪽: 로고 소개 + 링크 묶음 ===== */}
        <div className="footer-top">
          {/* 왼쪽: 로고와 한 줄 소개 */}
          <div className="footer-brand">
            <span className="footer-logo">생각한줄</span>
            <p>
              흩어진 생각을 구조화하고,
              <br />
              내 문장으로 완성하는 글쓰기 서비스
            </p>
          </div>

          {/* 오른쪽: 링크 묶음들 */}
          <div className="footer-links">
            {/* 바깥 map: 묶음(서비스, 고객지원)을 하나씩 */}
            {FOOTER_LINKS.map((group) => (
              <div key={group.title} className="footer-link-group">
                <strong>{group.title}</strong>
                <ul>
                  {/* 안쪽 map: 묶음 안의 링크를 하나씩 */}
                  {group.links.map((link) => (
                    <li key={link.key}>
                      <button onClick={() => handleClick(link.key)}>{link.label}</button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* ===== 아래쪽: 팀 정보 + 저작권 ===== */}
        <div className="footer-bottom">
          {/* 두 항목을 각각 span으로 감싸서, 모바일에서는 두 줄로 나눠 보이게 함 (CSS) */}
          <p className="footer-team">
            <span>경동대학교 컴퓨터공학과 2026 졸업작품</span>
            {/* 항목 사이 구분선(|) — 모바일에서는 숨김 */}
            <span className="divider" aria-hidden="true">|</span>
            <span>팀 글쓴이 · 이학현, 강민수, 한세빈</span>
          </p>
          {/*
            &copy; : © 기호를 HTML로 쓰는 방법
            new Date().getFullYear(): 지금 연도를 자동으로 가져옴 (해가 바뀌어도 고칠 필요 없음)
          */}
          <p className="footer-copy">&copy; {new Date().getFullYear()} 생각한줄. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
