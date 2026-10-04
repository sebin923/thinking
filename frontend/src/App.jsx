import { useEffect, useState } from "react";

function App() {
  const [message, setMessage] = useState("연결 확인 중...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/test")
        .then((response) => response.json())
        .then((data) => {
          setMessage(data.message);
        })
        .catch((error) => {
          console.error(error);
          setMessage("서버 연결 실패");
        });
  }, []);

  return (
      <div>
        <h1>생각한줄</h1>
        <p>{message}</p>
      </div>
  );
}

export default App;