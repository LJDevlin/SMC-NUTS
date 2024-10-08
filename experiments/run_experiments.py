import json
from pathlib import Path
import numpy as np
import seaborn as sns
from scipy.stats import multivariate_normal

from smcnuts.smc_sampler import SMCSampler
from smcnuts.model.bridgestan import StanModel


sns.set_style("whitegrid")

"""
Script to run the SMC-sampler with different configurations for multiple Monte Carlo runs

The three configurations are:

i) An SMC-sampler using accept-reject
ii) An SMC-sampler parameterised by using the forwards proposal as the L-kernel
iii) An SMC-sampler parameterised by using a Gaussian approximation to the optimal-L kernel. 

Options:
N_MCMC_RUNS: Number of Monte Carlo runs
N: The number of iterations the sampler is ran for
k: THe number of samples used
Model_name: The name of the stan model being used, must be placed in '../stan_models/'

SMC configurations:
tempering : Set a tempering mechanism, default is None
sample_proposal : = Set an initial distribution of samples
step_size : step size for the numerical integration. Taken from '../stan_models/$Model_name$/config_model.json', otherwise defaults to 0.5
momentum_proposal : Set a distribution from which to sample a momentum value
accept_reject : Turn on the accept_reject mechanism
lkernel: Set L-kernel. Matching configurations above asymptoptic with temprering (i), forward_lkernel (ii), and gauss_lkernel (iii)
"""

#Number of Monte-Carlo runs
N_MCMC_RUNS = 25

# Sampler configurations
N = 100 #Number of samples
K = 15 #Number of iterations

# Specify model - CHANGE THIS TO CHANGE STAN MODEL
# Note: The stan file has been modified to include a temperature variable "phi" which is used in all likelihood terms within the stan model block
# Phi is updated within the SMC code via the data to allow us to calclulate the tempered model at the required instances.
model_name = "arma"


def main():

    # Path to the output directory
    output_dir = Path.joinpath(Path.cwd(), "output", model_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load Stan model
    model_dir = Path.joinpath(Path.cwd().parent, "stan_models", model_name)
    model_path = Path.joinpath(model_dir, f"{model_name}.stan")
    if not model_path.exists():
        raise FileNotFoundError(f"Stan model {model_name} not found.")

    # Check for data
    model_data_path = Path.joinpath(model_dir, f"{model_name}.json")
    if not model_data_path.exists():
        model_data_path = None

    # Load ground truth from Stan model directory
    true_mean = []
    true_var = []
    ground_truth_path = Path.joinpath(model_dir, f"{model_name}.params")
    with open(ground_truth_path, "r") as f:
        for line in f:
            mean = line.split()[1]
            variance = line.split()[2]
            true_mean.append(float(mean))
            true_var.append(float(variance))

    # Load model_config
    model_config_path = Path.joinpath(model_dir, f"model_config.json")
    if model_config_path.exists():
        with open(model_config_path, "r") as f:
            model_config = json.load(f)
    else:
        model_config = None
    
    # Load Step-size from model_config file
    if model_config is not None and "step_size" in model_config.keys():
        step_size = model_config["step_size"]
    else:
        step_size = 0.5


    # Load Stan model
    target = StanModel(model_name=model_name, model_path=str(model_path), data_path=str(model_data_path))


    print(f"Model: {model_name}")
    print(f"K: {K}")
    print(f"N: {N}")
    print(f"step_size: {step_size}")

    for i in range(N_MCMC_RUNS): # For each Monte Carlo run
        print(f"\nMCMC Run {i + 1} of {N_MCMC_RUNS}")
        
        # Fix seed for particular iterations
        rng = np.random.RandomState(10 * (i + 1))
        initial_state = rng.get_state()

        # Initialize sampler initial distribution and momentum distribution
        sample_proposal = multivariate_normal(mean=np.zeros(target.dim), cov=np.eye(target.dim), seed=rng)
        momentum_proposal = multivariate_normal(mean=np.zeros(target.dim), cov=np.eye(target.dim), seed=rng)
       
        """
        Run SMC sampler with the Forwards-proposal L-kernel
        """

        print("Sampling with Forward Proposal L Kernel")
        fp_nuts_smcs = SMCSampler(
            K=K,
            N=N,
            target=target,
            step_size=step_size,
            sample_proposal=sample_proposal,
            momentum_proposal=momentum_proposal,
            lkernel="forwardsLKernel",
            tempering=False,
            rng=rng,
        )

        fp_nuts_smcs.sample()

        print(f"\nFinished sampling in {fp_nuts_smcs.run_time} seconds")
        
        # Save output to csv
        save_output(fp_nuts_smcs, "forward_lkernel", i, output_dir)
        
        """
        Run SMC sampler with the Gaussian approximation to the optimal L-kernel
        """
        
        print("Sampling with Gaussian Approximation L Kernel")
        rng.set_state(initial_state) # reset rng seed

        gauss_nuts_smcs = SMCSampler(
            K=K,
            N=N,
            target=target,
            step_size=step_size,
            sample_proposal=sample_proposal,
            momentum_proposal=momentum_proposal,
            lkernel="GaussianApproxLKernel",
            tempering=False,
            rng=rng,
        )
        rng.set_state(initial_state)
        gauss_nuts_smcs.sample()

        print(f"\nFinished sampling in {gauss_nuts_smcs.run_time} seconds")
        
        # Save output to csv
        save_output(gauss_nuts_smcs, "gaussian_lkernel", i, output_dir)

        """
        Run SMC sampler with the asymptotic approximation to the optimal L-kernal (with tempering)
        """
        
        print("Sampling with Asymptotically Optimal L Kernel with Adaptive Tempering and Accept/Reject")
        rng.set_state(initial_state)
        tempered_nuts_smcs = SMCSampler(
            K=K,
            N=N,
            target=target,
            step_size=step_size,
            sample_proposal=sample_proposal,
            momentum_proposal=momentum_proposal,
            lkernel="asymptoticLKernel",
            tempering=True,
            rng=rng,
        )


        tempered_nuts_smcs.sample()


        print(f"\nFinished sampling in {tempered_nuts_smcs.run_time} seconds")

        # Save output to csv
        save_output(tempered_nuts_smcs, "asymptotic_lkernel", i, output_dir)

        # End MC loop
 
        


def save_output(SMC, strategy, i, output_dir):
    """
    Function to save output to file
    parameters saved:
    mean estimates, variance estimates, Effective sample size (ESS), temperature (phi), acceptance rate
    
    """
    
    path = Path.joinpath(output_dir, strategy)
    path.mkdir(parents=True, exist_ok=True)

    mean_estimate_path = Path.joinpath(path, f"mean_estimate_{i}.csv")
    np.savetxt(mean_estimate_path, SMC.mean_estimate, delimiter=",")
    var_estimate_path = Path.joinpath(path, f"var_estimate_{i}.csv")
    np.savetxt(var_estimate_path, SMC.variance_estimate, delimiter=",")
    ess_path = Path.joinpath(path, f"ess_{i}.csv")
    np.savetxt(ess_path, SMC.ess, delimiter=",")
    phi_path = Path.joinpath(path, f"phi_{i}.csv")
    np.savetxt(phi_path, SMC.phi, delimiter=",")
    acceptance_rate_path = Path.joinpath(path, f"acceptance_rate_{i}.csv")
    np.savetxt(acceptance_rate_path, SMC.acceptance_rate, delimiter=",")

if __name__ == "__main__":
    main()
