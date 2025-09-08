import express from "express";
import mongoose from "mongoose";
import cors from "cors";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import dotenv from "dotenv";
import multer from "multer";
import axios from "axios";
import fs from "fs";
import FormData from "form-data";

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

// Enhanced document schema with classification results and jargon analysis
const documentSchema = new mongoose.Schema({
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  fileName: String,
  uploadDate: { type: Date, default: Date.now },
  status: { type: String, enum: ['uploaded', 'processing', 'analyzed', 'error'], default: 'uploaded' },
  classification: {
    type: String,
    default: null
  },
  confidence: {
    type: Number,
    default: null
  },
  keyTerms: [{
    type: String
  }],
  summary: String,
  importantDates: [{
    type: { type: String },
    date: String
  }],
  partiesInvolved: [{
    type: String
  }],
  // New fields for jargon analysis
  jargonAnalysis: {
    jargonsFound: {
      type: Map,
      of: {
        meaning: String,
        occurrences: Number,
        originalTerm: String
      },
      default: new Map()
    },
    simplifiedText: String,
    totalJargons: { type: Number, default: 0 },
    jargonSummary: String,
    complexityAnalysis: {
      complexity: String,
      score: Number,
      jargonCount: Number,
      totalWords: Number
    }
  }
});

const Document = mongoose.model("Document", documentSchema);

const authMiddleware = (req, res, next) => {
  try {
    const token = req.headers.authorization?.split(" ")[1];
    if (!token) {
      return res.status(401).json({ message: "No token provided, authorization denied" });
    }
    
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded.id;
    next();
  } catch (err) {
    res.status(401).json({ message: "Token is not valid" });
  }
};

// Auth routes
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

app.get("/profile", authMiddleware, async (req, res) => {
  try {
    const user = await User.findById(req.user).select("-password");
    if (!user) {
      return res.status(404).json({ message: "User not found" });
    }
    res.json(user);
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

app.get("/documents", authMiddleware, async (req, res) => {
  try {
    const documents = await Document.find({ userId: req.user }).sort({ uploadDate: -1 });
    res.json(documents);
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// Get specific document details
app.get("/documents/:id", authMiddleware, async (req, res) => {
  try {
    const document = await Document.findOne({ 
      _id: req.params.id, 
      userId: req.user 
    });
    
    if (!document) {
      return res.status(404).json({ message: "Document not found" });
    }
    
    res.json(document);
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// Enhanced upload endpoint with model integration
const upload = multer({ 
  dest: 'uploads/',
  fileFilter: (req, file, cb) => {
    if (file.mimetype === 'application/pdf') {
      cb(null, true);
    } else {
      cb(new Error('Only PDF files are allowed'));
    }
  },
  limits: {
    fileSize: 10 * 1024 * 1024 // 10MB limit
  }
});

app.post("/upload", authMiddleware, upload.single('document'), async (req, res) => {
  let tempDocument = null;
  
  try {
    if (!req.file) {
      return res.status(400).json({ message: "No document file uploaded" });
    }

    // Create document record with initial status
    tempDocument = new Document({
      userId: req.user,
      fileName: req.file.originalname,
      status: 'processing'
    });
    await tempDocument.save();

    // Send file to Python model API
    const formData = new FormData();
    formData.append('file', fs.createReadStream(req.file.path), {
      filename: req.file.originalname,
      contentType: req.file.mimetype
    });

    const modelApiUrl = 'http://localhost:5001/classify';
    const response = await axios.post(modelApiUrl, formData, {
      headers: {
        ...formData.getHeaders(),
      },
      timeout: 30000 // 30 second timeout
    });

    if (response.data.success) {
      // Update document with classification results and jargon analysis
      tempDocument.status = 'analyzed';
      tempDocument.classification = response.data.classification;
      tempDocument.confidence = response.data.confidence;
      tempDocument.keyTerms = response.data.key_terms;
      tempDocument.summary = response.data.summary;
      tempDocument.importantDates = response.data.important_dates;
      tempDocument.partiesInvolved = response.data.parties_involved;
      
      // Add jargon analysis data
      if (response.data.jargon_analysis) {
        const jargonAnalysisData = {
          jargonsFound: new Map(),
          simplifiedText: response.data.jargon_analysis.simplified_text || '',
          totalJargons: response.data.jargon_analysis.total_jargons || 0,
          jargonSummary: response.data.jargon_analysis.jargon_summary || '',
          complexityAnalysis: response.data.jargon_analysis.complexity_analysis || {
            complexity: 'Unknown',
            score: 0,
            jargonCount: 0,
            totalWords: 0
          }
        };

        // Convert jargons_found object to Map format for MongoDB
        if (response.data.jargon_analysis.jargons_found) {
          for (const [jargon, info] of Object.entries(response.data.jargon_analysis.jargons_found)) {
            jargonAnalysisData.jargonsFound.set(jargon, {
              meaning: info.meaning,
              occurrences: info.occurrences,
              originalTerm: info.original_term || jargon
            });
          }
        }

        tempDocument.jargonAnalysis = jargonAnalysisData;
      }
      
      await tempDocument.save();

      // Clean up the temporary uploaded file
      fs.unlinkSync(req.file.path);

      res.status(200).json({ 
        message: "Document uploaded and analyzed successfully",
        document: tempDocument
      });
    } else {
      throw new Error('Model classification failed');
    }

  } catch (error) {
    console.error("Error during document processing:", error);
    
    // Update document status to error if it was created
    if (tempDocument) {
      tempDocument.status = 'error';
      await tempDocument.save();
    }
    
    // Clean up the temporary file
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }

    // Return appropriate error message
    let errorMessage = "Document processing failed";
    if (error.code === 'ECONNREFUSED') {
      errorMessage = "Model service is not available. Please try again later.";
    } else if (error.response) {
      errorMessage = error.response.data?.error || "Model processing error";
    }

    res.status(500).json({ message: errorMessage });
  }
});

// New endpoint for standalone jargon simplification
app.post("/simplify-jargons", authMiddleware, async (req, res) => {
  try {
    const { text } = req.body;
    
    if (!text) {
      return res.status(400).json({ message: "No text provided" });
    }

    const response = await axios.post('http://localhost:5001/simplify-jargons', {
      text: text
    }, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 15000
    });

    if (response.data.success) {
      res.json({
        success: true,
        original_text: response.data.original_text,
        simplified_text: response.data.simplified_text,
        jargons_found: response.data.jargons_found,
        total_jargons: response.data.total_jargons,
        complexity_analysis: response.data.complexity_analysis,
        jargon_summary: response.data.jargon_summary
      });
    } else {
      throw new Error('Jargon simplification failed');
    }

  } catch (error) {
    console.error("Error during jargon simplification:", error);
    
    let errorMessage = "Jargon simplification failed";
    if (error.code === 'ECONNREFUSED') {
      errorMessage = "Model service is not available. Please try again later.";
    } else if (error.response) {
      errorMessage = error.response.data?.error || "Jargon simplification error";
    }

    res.status(500).json({ message: errorMessage });
  }
});

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({ 
    status: 'healthy', 
    service: 'backend-api',
    timestamp: new Date().toISOString()
  });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () =>
  console.log(`🚀 Backend API running on http://localhost:${PORT}`)
);