// In-Browser Meeting Recorder Logic

let audioCtx = null;
let mediaRecorder = null;
let recordedChunks = [];
let screenStream = null;
let micStream = null;
let combinedStream = null;
let visualizerAnalyser = null;
let drawVisual = null;
let secondsRecorded = 0;
let timerInterval = null;
let recordedBlob = null;
let selectedSource = 'screen'; // default

// Web Speech API
let recognition = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  
  recognition.onresult = (event) => {
    let interimTranscript = '';
    let finalTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }
    const box = document.getElementById('live-transcription-box');
    if (box) {
      box.textContent = finalTranscript || interimTranscript || "Listening...";
    }
  };
}

// Toast Helper
function showToast(message) {
  const toast = document.getElementById('toast');
  if (toast) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 4000);
  }
}

// Get selected source
function getSelectedSource() {
  return selectedSource;
}

// Populate Microphones list
async function loadMicrophones() {
  const select = document.getElementById('mic-select');
  if (!select) return;
  
  try {
    // Request permission to query devices
    await navigator.mediaDevices.getUserMedia({ audio: true });
    
    const devices = await navigator.mediaDevices.enumerateDevices();
    select.innerHTML = '';
    
    const audioDevices = devices.filter(d => d.kind === 'audioinput');
    audioDevices.forEach(device => {
      const option = document.createElement('option');
      option.value = device.deviceId;
      option.textContent = device.label || `Microphone ${select.length + 1}`;
      select.appendChild(option);
    });
  } catch (err) {
    console.error("Error loading microphones:", err);
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Default Microphone';
    select.appendChild(option);
  }
}

// Handle source button click
document.querySelectorAll('.source-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.source-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedSource = btn.dataset.source;
  });
});

// Setup canvas visualizer
function setupVisualizer(stream) {
  const canvas = document.getElementById('canvas');
  if (!canvas) return;
  const canvasCtx = canvas.getContext('2d');
  
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  
  const sourceNode = audioCtx.createMediaStreamSource(stream);
  visualizerAnalyser = audioCtx.createAnalyser();
  visualizerAnalyser.fftSize = 256;
  sourceNode.connect(visualizerAnalyser);
  
  const bufferLength = visualizerAnalyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  
  function draw() {
    drawVisual = requestAnimationFrame(draw);
    visualizerAnalyser.getByteFrequencyData(dataArray);
    
    canvasCtx.fillStyle = 'rgba(8, 8, 16, 1)';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    
    const barWidth = (canvas.width / bufferLength) * 2.5;
    let barHeight;
    let x = 0;
    
    for (let i = 0; i < bufferLength; i++) {
      barHeight = dataArray[i] / 2;
      
      // Draw smooth wave colors
      canvasCtx.fillStyle = `rgb(${barHeight + 100}, 142, 247)`;
      canvasCtx.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);
      
      x += barWidth + 1;
    }
  }
  
  draw();
}

// Timer helpers
function startTimer() {
  secondsRecorded = 0;
  const timerEl = document.getElementById('timer');
  timerInterval = setInterval(() => {
    secondsRecorded++;
    const mins = Math.floor(secondsRecorded / 60).toString().padStart(2, '0');
    const secs = (secondsRecorded % 60).toString().padStart(2, '0');
    timerEl.textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

// Stop all media tracks
function stopTracks() {
  stopTimer();
  
  if (drawVisual) {
    cancelAnimationFrame(drawVisual);
    drawVisual = null;
  }
  
  if (screenStream) {
    screenStream.getTracks().forEach(t => t.stop());
    screenStream = null;
  }
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  
  if (audioCtx && audioCtx.state !== 'closed') {
    audioCtx.close();
    audioCtx = null;
  }
  
  if (recognition) {
    try { recognition.stop(); } catch(e) {}
  }
}

// Setup start recording listener
document.getElementById('start-session-btn').addEventListener('click', async () => {
  recordedChunks = [];
  const source = getSelectedSource();
  const recordMic = document.getElementById('mic-toggle').checked;
  const recordSys = document.getElementById('system-audio-toggle').checked;
  const micId = document.getElementById('mic-select').value;
  
  try {
    let screenTracks = [];
    let systemAudioTracks = [];
    
    const displayConstraints = {
      video: {
        displaySurface: source === 'screen' ? 'monitor' : source
      },
      audio: recordSys
    };
    
    // Capture display
    screenStream = await navigator.mediaDevices.getDisplayMedia(displayConstraints);
    screenTracks = screenStream.getVideoTracks();
    systemAudioTracks = screenStream.getAudioTracks();
    
    let micTracks = [];
    if (recordMic) {
      try {
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: micId ? { deviceId: { exact: micId } } : true
        });
        micTracks = micStream.getAudioTracks();
      } catch (micErr) {
        console.warn("Failed to get mic stream:", micErr);
        showToast("Warning: Microphone access denied. Capturing system audio only.");
      }
    }
    
    const audioTracksToMix = [...systemAudioTracks, ...micTracks];
    if (audioTracksToMix.length === 0) {
      throw new Error("No audio tracks captured. Enable mic or check display audio settings.");
    }
    
    if (audioTracksToMix.length > 1) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const dest = audioCtx.createMediaStreamDestination();
      
      audioTracksToMix.forEach(track => {
        const stream = new MediaStream([track]);
        const sourceNode = audioCtx.createMediaStreamSource(stream);
        sourceNode.connect(dest);
      });
      
      setupVisualizer(dest.stream);
      combinedStream = new MediaStream([
        ...screenTracks,
        ...dest.stream.getAudioTracks()
      ]);
    } else {
      const singleAudioStream = new MediaStream([audioTracksToMix[0]]);
      setupVisualizer(singleAudioStream);
      combinedStream = new MediaStream([
        ...screenTracks,
        audioTracksToMix[0]
      ]);
    }
    
    // Keep display stream alive for system audio but record only mixed audio to save space
    const audioOnlyStream = new MediaStream(combinedStream.getAudioTracks());
    let options = { mimeType: 'audio/webm;codecs=opus' };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options = { mimeType: 'audio/webm' };
    }
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options = {};
    }
    
    mediaRecorder = new MediaRecorder(audioOnlyStream, options);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        recordedChunks.push(e.data);
      }
    };
    
    mediaRecorder.onstop = () => {
      stopTracks();
      prepareReview();
    };
    
    mediaRecorder.start(1000);
    startTimer();
    
    if (recognition) {
      try { recognition.start(); } catch(e) {}
    }
    
    document.getElementById('setup-pane').style.display = 'none';
    document.getElementById('recording-pane').style.display = 'block';
    showToast("Recording session active!");
    
  } catch (err) {
    console.error("Recording setup error:", err);
    showToast("Error initializing: " + err.message);
    stopTracks();
  }
});

// Pause / Resume recording
const pauseBtn = document.getElementById('pause-btn');
pauseBtn.addEventListener('click', () => {
  if (!mediaRecorder) return;
  
  if (mediaRecorder.state === 'recording') {
    mediaRecorder.pause();
    stopTimer();
    pauseBtn.textContent = 'Resume';
    document.getElementById('status-text').textContent = 'Paused';
    if (recognition) {
      try { recognition.stop(); } catch(e) {}
    }
  } else if (mediaRecorder.state === 'paused') {
    mediaRecorder.resume();
    // Resume timer count
    const timerEl = document.getElementById('timer');
    timerInterval = setInterval(() => {
      secondsRecorded++;
      const mins = Math.floor(secondsRecorded / 60).toString().padStart(2, '0');
      const secs = (secondsRecorded % 60).toString().padStart(2, '0');
      timerEl.textContent = `${mins}:${secs}`;
    }, 1000);
    
    pauseBtn.textContent = 'Pause';
    document.getElementById('status-text').textContent = 'Capturing...';
    if (recognition) {
      try { recognition.start(); } catch(e) {}
    }
  }
});

// Stop recording
document.getElementById('stop-btn').addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
});

// Prepare Review UI
function prepareReview() {
  recordedBlob = new Blob(recordedChunks, { type: 'audio/webm' });
  const audioUrl = URL.createObjectURL(recordedBlob);
  
  const player = document.getElementById('audio-player');
  player.src = audioUrl;
  
  // Set default suggested title
  const dateStr = new Date().toISOString().split('T')[0];
  document.getElementById('meeting-title').value = `Meeting - ${dateStr}`;
  
  document.getElementById('recording-pane').style.display = 'none';
  document.getElementById('review-pane').style.display = 'block';
}

// Discard recording
document.getElementById('discard-btn').addEventListener('click', (e) => {
  e.preventDefault();
  if (confirm("Are you sure you want to discard this recording?")) {
    resetRecorder();
  }
});

function resetRecorder() {
  recordedChunks = [];
  recordedBlob = null;
  document.getElementById('review-pane').style.display = 'none';
  document.getElementById('setup-pane').style.display = 'block';
  document.getElementById('timer').textContent = '00:00';
  document.getElementById('live-transcription-box').textContent = 'Speech-to-text preview will appear here as you speak...';
  document.getElementById('upload-progress-container').style.display = 'none';
  const player = document.getElementById('audio-player');
  player.src = '';
}

// Upload & Process recording
document.getElementById('upload-btn').addEventListener('click', async () => {
  const title = document.getElementById('meeting-title').value.trim();
  const language = document.getElementById('language-select').value;
  
  if (!title) {
    showToast("Please enter a meeting title.");
    return;
  }
  
  if (!recordedBlob) {
    showToast("No recorded audio available.");
    return;
  }
  
  const uploadBtn = document.getElementById('upload-btn');
  const progressContainer = document.getElementById('upload-progress-container');
  const progressBar = document.getElementById('upload-progress-bar');
  const progressPercent = document.getElementById('upload-percent');
  
  uploadBtn.disabled = true;
  uploadBtn.textContent = 'Uploading...';
  progressContainer.style.display = 'block';
  
  const formData = new FormData();
  formData.append('file', recordedBlob, 'recording.webm');
  formData.append('title', title);
  formData.append('language', language);
  
  // Custom XHR to track progress
  const xhr = new XMLHttpRequest();
  xhr.open('POST', `${API_BASE_URL}/api/v1/meetings/upload`);
  
  const token = localStorage.getItem('meetmind_token');
  if (token) {
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
  }
  
  // CSRF token
  const csrfToken = getCookie('csrf_token');
  if (csrfToken) {
    xhr.setRequestHeader('X-CSRF-Token', csrfToken);
  }
  
  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      const percent = Math.round((event.loaded / event.total) * 100);
      progressBar.style.width = percent + '%';
      progressPercent.textContent = percent + '%';
      if (percent >= 100) {
        uploadBtn.textContent = 'AI Processing (may take 1-2 mins)...';
      }
    }
  };
  
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        const resData = JSON.parse(xhr.responseText);
        showToast("Recording uploaded successfully!");
        
        // Setup browser completion notification
        if (Notification.permission === "granted") {
          new Notification("Meeting Uploaded", {
            body: `"${title}" has been uploaded and is being processed by AI.`
          });
        }
        
        // Redirect to dashboard
        setTimeout(() => {
          window.location.href = 'dashboard.html';
        }, 1500);
      } catch (err) {
        showToast("Error processing server response.");
        resetUploadUI();
      }
    } else {
      let errMsg = "Upload failed. Please try again.";
      try {
        const resData = JSON.parse(xhr.responseText);
        errMsg = resData.detail || errMsg;
      } catch(e) {}
      showToast(errMsg);
      resetUploadUI();
    }
  };
  
  xhr.onerror = () => {
    showToast("Network error during upload.");
    resetUploadUI();
  };
  
  xhr.send(formData);
});

function resetUploadUI() {
  const uploadBtn = document.getElementById('upload-btn');
  uploadBtn.disabled = false;
  uploadBtn.textContent = 'Process with AI';
  document.getElementById('upload-progress-container').style.display = 'none';
}

// Request permission for browser notifications on load
if ("Notification" in window && Notification.permission === "default") {
  Notification.requestPermission();
}

// Load Microphones list on startup
loadMicrophones();
