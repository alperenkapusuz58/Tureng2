(function () {
    const EDITOR_SELECTOR = 'textarea[data-richtext="true"]';
    const TINYMCE_CDN = 'https://cdn.jsdelivr.net/npm/tinymce@7/tinymce.min.js';

    function initTinyMCE() {
        if (!window.tinymce) {
            return;
        }
        const root = document.documentElement;
        const isDark =
            root.dataset.theme === 'dark' ||
            root.classList.contains('theme-dark') ||
            window.matchMedia('(prefers-color-scheme: dark)').matches;

        window.tinymce.remove(EDITOR_SELECTOR);
        window.tinymce.init({
            selector: EDITOR_SELECTOR,
            height: 210,
            menubar: false,
            branding: false,
            statusbar: false,
            plugins: 'autolink paste',
            toolbar: 'undo redo | bold italic underline | removeformat',
            browser_spellcheck: true,
            paste_as_text: false,
            forced_root_block: 'p',
            skin: isDark ? 'oxide-dark' : 'oxide',
            content_css: isDark ? 'dark' : 'default',
            content_style: isDark
                ? 'body { background:#111827; color:#e5e7eb; } p { margin: 0 0 10px; }'
                : 'body { background:#ffffff; color:#111827; } p { margin: 0 0 10px; }',
            setup: function (editor) {
                editor.on('change keyup blur', function () {
                    editor.save();
                });
            },
        });
    }

    function loadTinyMCEScript() {
        if (window.tinymce) {
            initTinyMCE();
            return;
        }

        const existing = document.querySelector('script[data-tinymce-loader="1"]');
        if (existing) {
            existing.addEventListener('load', initTinyMCE, { once: true });
            return;
        }

        const script = document.createElement('script');
        script.src = TINYMCE_CDN;
        script.referrerPolicy = 'origin';
        script.dataset.tinymceLoader = '1';
        script.addEventListener('load', initTinyMCE, { once: true });
        document.head.appendChild(script);
    }

    function bootstrap() {
        if (!document.querySelector(EDITOR_SELECTOR)) {
            return;
        }
        loadTinyMCEScript();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
        bootstrap();
    }
})();
