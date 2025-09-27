// Smooth scrolling for navigation links
document.addEventListener('DOMContentLoaded', function() {
    // Handle navigation clicks
    const navLinks = document.querySelectorAll('.nav-menu a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            if (targetSection) {
                targetSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Highlight active navigation item
    function highlightActiveNav() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-menu a');

        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (window.scrollY >= (sectionTop - 200)) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + current) {
                link.classList.add('active');
            }
        });
    }

    window.addEventListener('scroll', highlightActiveNav);

    // Add fade-in animation for feature cards
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe feature cards and other animated elements
    const animatedElements = document.querySelectorAll('.feature-card, .setup-step, .example-card');
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

    // Copy to clipboard functionality for code blocks
    const codeBlocks = document.querySelectorAll('pre code');
    codeBlocks.forEach(block => {
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copy to clipboard';

        const pre = block.parentElement;
        pre.style.position = 'relative';
        pre.appendChild(button);

        button.addEventListener('click', function() {
            navigator.clipboard.writeText(block.textContent).then(() => {
                button.innerHTML = '<i class="fas fa-check"></i>';
                button.style.color = '#48bb78';
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-copy"></i>';
                    button.style.color = '';
                }, 2000);
            });
        });
    });

    // Mobile menu toggle (if needed in future)
    const mobileMenuButton = document.querySelector('.mobile-menu-button');
    const navMenu = document.querySelector('.nav-menu');

    if (mobileMenuButton) {
        mobileMenuButton.addEventListener('click', function() {
            navMenu.classList.toggle('active');
        });
    }

    // Parallax effect for hero section
    window.addEventListener('scroll', function() {
        const scrolled = window.pageYOffset;
        const hero = document.querySelector('.hero');
        if (hero) {
            hero.style.transform = `translateY(${scrolled * 0.5}px)`;
        }
    });

    // Add loading animation
    document.body.classList.add('loaded');
});

// Add CSS for copy button and loading
const style = document.createElement('style');
style.textContent = `
    .copy-button {
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(255, 255, 255, 0.1);
        border: none;
        color: #e2e8f0;
        padding: 8px;
        border-radius: 4px;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.3s, background 0.3s;
    }

    pre:hover .copy-button {
        opacity: 1;
    }

    .copy-button:hover {
        background: rgba(255, 255, 255, 0.2);
    }

    .nav-menu a.active {
        opacity: 1;
        border-bottom: 2px solid #ffd700;
        padding-bottom: 2px;
    }

    body {
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    body.loaded {
        opacity: 1;
    }

    @media (max-width: 768px) {
        .nav-menu {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            flex-direction: column;
            padding: 1rem;
            transform: translateY(-100%);
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }

        .nav-menu.active {
            transform: translateY(0);
            opacity: 1;
            visibility: visible;
        }

        .mobile-menu-button {
            display: block;
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
        }
    }

    @media (min-width: 769px) {
        .mobile-menu-button {
            display: none;
        }
    }
`;
document.head.appendChild(style);