import autograd.numpy as np
from scipy.stats import multivariate_normal
from .utils import hmc_accept_reject
from smcnuts.proposal.nuts_acc_rej import NUTSProposal_with_AccRej

# Set max tree death of NUTS tree, default is 2^10.
MAX_TREE_DEPTH = 10

class NUTSProposal_with_AccRej_tempering(NUTSProposal_with_AccRej):
    """No-U-Turn Sampler Proposal

    Propagate samples using the proposal from the No-U-Turn proposal [1]. Algorithm is largely based on Alg. 3 of the reference. 


    [1] https://www.jmlr.org/papers/volume15/hoffman14a/hoffman14a.pdf

    Attributes:
        target: Target distribution of interest.
        dim: Dimensionality of the system.
        momentum_proposal: Momentum proposal distribution.
        step_size: Step size for the leapfrog integrator.
        
    """

    def rvs(self, x_cond, r_cond, grad_x, phi: float = 1.0):
        """
        Description:
            Propogate a set of samples using the proposal from the No-U-Turn Sampler.

        Args:
            x_cond: Current particle positions.
            r_cond: Current particle momenta.
            grad_x: Current particle gradients.

        Returns:
            x_prime: Updated particle positions.
            r_prime: Updated particle momenta.
        """

        x_prime, r_prime = super(NUTSProposal_with_AccRej_tempering, self).rvs(x_cond, r_cond, grad_x, phi)

     
        p_logpdf_x_new_phi_old = self.target.logpdf(x_prime, phi=phi_new)
        args = [x_prime, p_logpdf_x_new_phi_old, phi_new]
        phi_new = self.tempering.calculate_phi(args)


        return x_prime, r_prime, phi_new