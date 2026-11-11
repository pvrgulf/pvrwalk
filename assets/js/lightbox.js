/* =================================
   SHARED WEBSITE LIGHTBOX
   ================================= */

// Create lightbox HTML automatically

document.body.insertAdjacentHTML(
	"beforeend",
	`
    <dialog id="imageLightbox">

        <div class="lightbox-content">

            <div class="lightbox-image-wrap">

                <button type="button" id="closeImage"
                    aria-label="Close lightbox">×</button>

                <button type="button" id="prevImage"
                    class="nav-button">❮</button>

                <img src="" alt="">

                <p id="imageCaption" class="lightbox-caption" hidden></p>

                <button type="button" id="nextImage"
                    class="nav-button">❯</button>

            </div>

        </div>

    </dialog>
    `,
);

// Identify elements

const lightbox = document.getElementById("imageLightbox");
const largeImage = lightbox.querySelector("img");
const imageCaption = document.getElementById("imageCaption");

const prevButton = document.getElementById("prevImage");
const nextButton = document.getElementById("nextImage");
const closeButton = document.getElementById("closeImage");

let galleryImages = [];
let currentImage = 0;
let savedScrollPosition = 0;

// =================================
// OPEN IMAGE
// =================================

document.addEventListener("click", function (e) {
	const link = e.target.closest("a.zoom");
	if (!link) return;

	e.preventDefault();

	savedScrollPosition = window.scrollY;

	const gallery = link.dataset.gallery;

	galleryImages = gallery ? [...document.querySelectorAll("a.zoom[data-gallery]")].filter((item) => item.dataset.gallery === gallery) : [link];

	currentImage = galleryImages.indexOf(link);

	showImage();

	lightbox.showModal();
});

// =================================
// DISPLAY IMAGE
// =================================

function showImage() {
	const link = galleryImages[currentImage];
	const thumbnail = link.querySelector("img");

	largeImage.src = link.href;
	largeImage.alt = thumbnail ? thumbnail.alt : "";

	// Only display a caption when one has been supplied.
	const caption = link.dataset.caption || "";

	imageCaption.textContent = caption;
	imageCaption.hidden = !caption;

	lightbox.classList.toggle("has-caption", Boolean(caption));

	prevButton.style.display = galleryImages.length > 1 ? "block" : "none";

	nextButton.style.display = galleryImages.length > 1 ? "block" : "none";
}

// =================================
// PREVIOUS IMAGE
// =================================

prevButton.addEventListener("click", function () {
	currentImage = (currentImage - 1 + galleryImages.length) % galleryImages.length;

	showImage();
});

// =================================
// NEXT IMAGE
// =================================

nextButton.addEventListener("click", function () {
	currentImage = (currentImage + 1) % galleryImages.length;

	showImage();
});

// =================================
// CLOSE BUTTON
// =================================

closeButton.addEventListener("click", function () {
	lightbox.close();
});

// =================================
// CLOSE OUTSIDE IMAGE
// =================================

lightbox.addEventListener("click", function (e) {
	if (e.target === lightbox || e.target === lightbox.querySelector(".lightbox-content")) {
		lightbox.close();
	}
});

// =================================
// KEYBOARD NAVIGATION
// =================================

document.addEventListener("keydown", function (e) {
	if (!lightbox.open || galleryImages.length < 2) return;

	if (e.key === "ArrowRight") nextButton.click();
	if (e.key === "ArrowLeft") prevButton.click();
});

// =================================
// RESTORE PAGE POSITION
// =================================

lightbox.addEventListener("close", function () {
	window.scrollTo(0, savedScrollPosition);
});
