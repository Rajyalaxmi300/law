import express from "express";
import mongoose from "mongoose";
import cors from "cors";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors({ origin: "http://localhost:5173", credentials: true }));

mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log("✅ MongoDB connected"))
  .catch(err => console.error("❌ Mongo error:", err.message));

const userSchema = new mongoose.Schema({
  firstName: String,
  lastName: String,
  email: { type: String, unique: true },
  password: String
});

const User = mongoose.model("User", userSchema);

// Middleware function to protect routes using JWT
const authMiddleware = (req, res, next) => {
  try {
    // Get the token from the 'Authorization' header
    const token = req.headers.authorization?.split(" ")[1];
    if (!token) {
      // If no token, return a 401 Unauthorized error
      return res.status(401).json({ message: "No token provided, authorization denied" });
    }
    
    // Verify the token using the secret key
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    // Attach the user's ID from the token to the request object
    req.user = decoded.id;
    next(); // Proceed to the next middleware or route handler
  } catch (err) {
    // If token verification fails, return a 401 Unauthorized error
    res.status(401).json({ message: "Token is not valid" });
  }
};

app.post("/signup", async (req, res) => {
  try {
    const { firstName, lastName, email, password } = req.body;
    const exists = await User.findOne({ email });
    if (exists) return res.status(400).json({ message: "User already exists" });

    const hashed = await bcrypt.hash(password, 10);
    await User.create({ firstName, lastName, email, password: hashed });
    res.status(201).json({ message: "User registered successfully" });
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

app.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;
    const user = await User.findOne({ email });
    if (!user) return res.status(400).json({ message: "Invalid credentials" });

    const ok = await bcrypt.compare(password, user.password);
    if (!ok) return res.status(400).json({ message: "Invalid credentials" });

    const token = jwt.sign({ id: user._id }, process.env.JWT_SECRET, { expiresIn: "1h" });
    res.json({ message: "Login successful", token });
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// New protected route to get user profile
// The authMiddleware is applied here to ensure only authenticated requests can access this route
app.get("/profile", authMiddleware, async (req, res) => {
  try {
    // Find the user by the ID attached by the middleware and exclude the password
    const user = await User.findById(req.user).select("-password");
    if (!user) {
      return res.status(404).json({ message: "User not found" });
    }
    res.json(user); // Send the user data back
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

app.listen(process.env.PORT || 5000, () =>
  console.log(`🚀 API running on http://localhost:${process.env.PORT || 5000}`)
);
