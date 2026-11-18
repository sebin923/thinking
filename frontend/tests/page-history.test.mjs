import assert from "node:assert/strict";
import test from "node:test";
import { createPageHistory, readPage } from "../src/utils/pageHistory.js";

// Model the browser's asynchronous traversal and state cloning, including an
// external page before the app. Restoring a blocked traversal must not push.
function browserAt(url = "https://example.test/", state = null) {
  const listeners = new Set();
  const entries = [{ url: "https://outside.test/", state: null }, { url, state }];
  let index = 1;
  let location = new URL(url);
  const history = {
    get state() { return structuredClone(entries[index].state); },
    get length() { return entries.length; },
    replaceState(state, unused, url) {
      location = new URL(url, location);
      entries[index] = { url: location.href, state: structuredClone(state) };
    },
    pushState(state, unused, url) {
      entries.splice(index + 1);
      location = new URL(url, location);
      entries.push({ url: location.href, state: structuredClone(state) });
      index += 1;
    },
    go(delta) {
      queueMicrotask(() => {
        const target = index + delta;
        if (target < 0 || target >= entries.length) return;
        index = target;
        location = new URL(entries[index].url);
        if (location.origin === "https://example.test") {
          for (const listener of listeners) listener({ state: history.state });
        }
      });
    },
    back() { history.go(-1); },
    forward() { history.go(1); },
  };
  const browser = {
    history,
    get location() { return location; },
    addEventListener(event, listener) { if (event === "popstate") listeners.add(listener); },
    removeEventListener(event, listener) { if (event === "popstate") listeners.delete(listener); },
  };
  // Real Window.location keeps its identity as the current address changes.
  const liveLocation = new Proxy({}, { get: (_, key) => location[key] });
  Object.defineProperty(browser, "location", { get: () => liveLocation });
  return browser;
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

test("menus, Back, Forward and repeated clicks preserve actual history", async () => {
  const browser = browserAt();
  let route;
  const navigation = createPageHistory(browser, { onChange: (next) => { route = next; } });
  assert.equal(browser.history.length, 2);
  navigation.navigate("about");
  navigation.navigate("quiz");
  navigation.navigate("quiz");
  assert.equal(browser.history.length, 4);
  assert.equal(browser.location.hash, "#/quiz");
  browser.history.back();
  await settle();
  assert.equal(route.page, "about");
  browser.history.forward();
  await settle();
  assert.equal(route.page, "quiz");
  browser.history.go(-2);
  await settle();
  assert.equal(route.page, "home");
  browser.history.back();
  await settle();
  assert.equal(browser.location.origin, "https://outside.test");
});

test("direct links and reload restore the screen without adding an entry", () => {
  const browser = browserAt("https://example.test/#/ranking");
  let route;
  const options = { onChange: (next) => { route = next; } };
  const first = createPageHistory(browser, options);
  assert.equal(route.page, "ranking");
  first.navigate("write", { data: { document: { id: 3 }, userId: 1 } });
  const length = browser.history.length;
  first.destroy();
  createPageHistory(browser, options);
  assert.equal(route.page, "write");
  assert.equal(route.data.document.id, 3);
  assert.equal(browser.history.length, length);
  assert.equal(readPage(new URL("https://example.test/#/unknown")), "home");
});

test("unsaved Back cancellation restores URL, screen and history; confirmation replays Back", async () => {
  const browser = browserAt();
  let route, retry;
  let dirty = true;
  const navigation = createPageHistory(browser, {
    onChange: (next) => { route = next; },
    shouldBlock: () => dirty,
    onBlocked: (resume) => { retry = resume; },
  });
  navigation.navigate("about");
  navigation.navigate("write");
  const length = browser.history.length;
  browser.history.go(-2);
  await settle();
  assert.equal(route.page, "write");
  assert.equal(browser.location.hash, "#/write");
  assert.equal(browser.history.length, length);
  // Cancel means not invoking retry. A second Back must still work.
  browser.history.back();
  await settle();
  assert.equal(browser.location.hash, "#/write");
  dirty = false;
  retry();
  await settle();
  assert.equal(route.page, "about");
  assert.equal(browser.history.length, length);
  browser.history.forward();
  await settle();
  assert.equal(route.page, "write");
});

test("Forward is blocked too and an obsolete confirmation cannot navigate", async () => {
  const browser = browserAt();
  let route, retry;
  let dirty = false;
  const navigation = createPageHistory(browser, {
    onChange: (next) => { route = next; },
    shouldBlock: () => dirty,
    onBlocked: (resume) => { retry = resume; },
  });
  navigation.navigate("write");
  navigation.navigate("quiz");
  browser.history.back();
  await settle();
  dirty = true;
  browser.history.forward();
  await settle();
  assert.equal(route.page, "write");
  assert.equal(browser.location.hash, "#/write");
  navigation.navigate("about");
  retry();
  await settle();
  assert.equal(route.page, "about");
});

test("settings Back preserves the selected document and avoids a navigation loop", async () => {
  const browser = browserAt();
  let route;
  const navigation = createPageHistory(browser, { onChange: (next) => { route = next; } });
  const data = { document: { id: 7, content: "저장된 본문" }, userId: 2 };
  navigation.navigate("write", { data });
  navigation.navigate("writing-settings", { data });
  navigation.back("write", data);
  await settle();
  assert.equal(route.page, "write");
  assert.deepEqual(route.data, data);
  browser.history.back();
  await settle();
  assert.equal(route.page, "home");

  const direct = browserAt("https://example.test/#/writing-settings");
  const directNavigation = createPageHistory(direct, { onChange: (next) => { route = next; } });
  directNavigation.back("write");
  assert.equal(route.page, "write");
  assert.equal(direct.history.length, 2);
});

test("payment callbacks are cleaned without exposing payment keys or breaking navigation", async () => {
  const browser = browserAt("https://example.test/payment/success?paymentKey=secret&orderId=order&amount=1000");
  let route;
  const navigation = createPageHistory(browser, {
    initialPage: "payment-result", onChange: (next) => { route = next; },
  });
  assert.equal(browser.location.pathname, "/");
  assert.equal(browser.location.search, "");
  assert.equal(route.page, "payment-result");
  assert.ok(!JSON.stringify(browser.history.state).includes("secret"));
  navigation.navigate("home");
  browser.history.back();
  await settle();
  assert.equal(route.page, "payment-result");
});

test("login redirects replace the form entry and branching discards the old Forward path", async () => {
  const browser = browserAt();
  let route;
  const navigation = createPageHistory(browser, { onChange: (next) => { route = next; } });
  navigation.navigate("login");
  navigation.navigate("mypage", { replace: true });
  browser.history.back();
  await settle();
  assert.equal(route.page, "home");
  navigation.navigate("quiz");
  browser.history.forward();
  await settle();
  assert.equal(route.page, "quiz");
  assert.equal(browser.history.length, 3);
});
