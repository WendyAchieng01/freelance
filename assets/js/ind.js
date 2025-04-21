console.log("hello");

// Get all elements with the class 'reveal'
const reveals = document.querySelectorAll(".reveal");

// Create a new Intersection Observer instance
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    // Check if the element is intersecting with the viewport
    if (entry.isIntersecting) {
      // Add the 'active' class to the element
      entry.target.classList.add("active");

      // Find the animation elements inside the container
      const animatedElements = entry.target.querySelectorAll(
        ".anim, .content-image, .container-rev"
      );

      // Add the animation classes to the elements
      animatedElements.forEach((element) => {
        element.classList.add("animate");
      });
    } else {
      // Remove the 'active' class from the element
      entry.target.classList.remove("active");

      // Find the animation elements inside the container
      const animatedElements = entry.target.querySelectorAll(
        ".anim, .content-image, .container-rev"
      );

      // Remove the animation classes from the elements
      animatedElements.forEach((element) => {
        element.classList.remove("animate");
      });
    }
  });
});

// Observe each element with the class 'reveal'
reveals.forEach((reveal) => {
  observer.observe(reveal);
});

//profile pic update
document.addEventListener("DOMContentLoaded", function () {
  const updatePicBtn = document.getElementById("update-pic-btn");
  const profilePicInput = document.getElementById("id_profile_pic");

  updatePicBtn.addEventListener("click", function () {
    profilePicInput.click();
  });

  profilePicInput.addEventListener("change", function () {
    const formData = new FormData();
    formData.append("profile_pic", profilePicInput.files[0]);

    fetch("/update-profile-pic/", {
      method: "POST",
      body: formData,
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
          .value,
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          console.log("Profile picture updated successfully");
          // Reload the page
          location.reload();
        } else {
          console.error("Error updating profile picture");
        }
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  });
});

//response.html
// Add this script at the end of your HTML file or in a separate JS file
const imageThumbnails = document.querySelectorAll(".thumbnail");
const imagePopup = document.querySelector(".image-popup");
const closeBtn = document.querySelector(".close-btn");

imageThumbnails.forEach((thumbnail) => {
  thumbnail.addEventListener("click", () => {
    const fullImage = thumbnail.nextElementSibling.querySelector(".full-image");
    fullImage.src = thumbnail.src;
    imagePopup.style.display = "block";
  });
});

closeBtn.addEventListener("click", () => {
  imagePopup.style.display = "none";
});

window.addEventListener("click", (event) => {
  if (event.target === imagePopup) {
    imagePopup.style.display = "none";
  }
});

//invoice.html
const lineItemContainer = document.getElementById("line-item-container");
const addLineItemBtn = document.getElementById("add-line-item");
addLineItemBtn.addEventListener("click", () => {
  const lineItemForm = document.querySelector(".line-item-form:last-child");
  const newLineItemForm = lineItemForm.cloneNode(true);

  // Create a new remove button
  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.classList.add("remove-line-item", "btn", "btn-danger");
  removeButton.textContent = "Remove";

  // Append the new remove button to the new line item form
  const lastCol = newLineItemForm.querySelector(".col-md-3:last-child");
  lastCol.appendChild(removeButton);

  lineItemContainer.appendChild(newLineItemForm);
});

lineItemContainer.addEventListener("click", (event) => {
  if (event.target.classList.contains("remove-line-item")) {
    event.target.closest(".line-item-form").remove();
  }
});

