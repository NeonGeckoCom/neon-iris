const sprite = document.querySelector(".sprite");

function triggerWake() {
  sprite.classList.remove("record", "waiting");
  sprite.classList.add("wake");
}

function triggerRecord() {
  sprite.classList.remove("wake", "waiting");
  sprite.classList.add("record");
}

function triggerWaiting() {
  sprite.classList.remove("wake", "record");
  sprite.classList.add("waiting");
}

function triggerDone() {
  sprite.classList.remove("wake", "record", "waiting");
}
