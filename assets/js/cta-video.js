        (function () {
            var src = 'https://stream.mux.com/8wrHPCX2dC3msyYU9ObwqNdm00u3ViXvOSHUMRYSEe5Q.m3u8';
            var videos = document.querySelectorAll('.cta-video');
            videos.forEach(function (video) {
                if (window.Hls && Hls.isSupported()) {
                    var hls = new Hls();
                    hls.loadSource(src);
                    hls.attachMedia(video);
                } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                    video.src = src;
                }
            });
        })();
    