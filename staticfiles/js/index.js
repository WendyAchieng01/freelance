console.log("hello");

// Close the dropdown if the user clicks outside of it
window.onclick = function (event) {
  if (!event.target.matches(".dropbtn")) {
    var dropdowns = document.getElementsByClassName("dropdown-menu");
    var i;
    for (i = 0; i < dropdowns.length; i++) {
      var openDropdown = dropdowns[i];
      if (openDropdown.classList.contains("show")) {
        openDropdown.classList.remove("show");
      }
    }
  }
};

// Toggle the dropdown content when the profile picture is clicked
var dropbtn = document.querySelector(".dropbtn");
dropbtn.addEventListener("click", function () {
  var dropdownMenu = this.nextElementSibling;
  dropdownMenu.classList.toggle("show");
});

//scroll
// Get all elements with the class 'reveal'
document.addEventListener("DOMContentLoaded", () => {
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
});
